"""HTTP surface of the learning host. Loopback only; course operations stay the state authority."""
import asyncio
import json
import logging
import os
import socket
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from .. import library
from ..store import OperationError
from .host import EventBus, Host, turn_summary
from .settings import TeacherSettings

log = logging.getLogger(__name__)
DIST = Path(__file__).resolve().parent.parent / 'web_dist'
MAX_BODY = 1024 * 1024
# An answer image is uploaded as its own raw body, so a phone photo fits; JSON bodies keep the small limit.
IMAGE_UPLOAD = '/api/practice/images'
MAX_IMAGE = 25 * 1024 * 1024


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class LessonRequest(Body):
    id: Optional[str] = None
    prompt: Optional[str] = None


class PreferencesRequest(Body):
    language: Literal['en', 'zh-CN']


class ResumeRequest(Body):
    request_id: str


class QuestionRequest(Body):
    id: Optional[str] = None
    question: str
    selection: Optional[str] = None
    selected_turn_id: Optional[str] = None
    main_turn_id: Optional[str] = None
    anchor: Optional[dict] = None
    pause: bool = False


class AnnotationRequest(Body):
    kind: Literal['highlight', 'note', 'bookmark']
    concept_id: Optional[str] = None
    passage: Optional[str] = None
    note: Optional[str] = None
    turn_id: Optional[str] = None
    task_id: Optional[str] = None
    source: Optional[dict] = None


class NoteRequest(Body):
    note: str


class MemoryRequest(Body):
    text: str


class ChoiceRequest(Body):
    choice: Literal['accept', 'decline']


class GenerateRequest(Body):
    concept_id: str


class PracticeRequest(Body):
    answer: Optional[str] = None
    images: Optional[list[str]] = None
    question: Optional[str] = None
    reason: Optional[str] = None


class NextSectionRequest(Body):
    concept_id: str
    request_id: str


class EnterSectionRequest(Body):
    concept_id: str
    request_id: str


class SkipChapterRequest(Body):
    request_id: str


class ReviewRequest(Body):
    concept_id: str


class RecapRequest(Body):
    id: Optional[str] = None


class SettingsRequest(Body):
    model: str = ''
    small_model: str = ''
    service_tier: str = ''
    small_effort: str = ''
    effort: str = 'medium'


class OpenCourseRequest(Body):
    name: str


class Courses:
    """The course library this host serves and the one course it owns at a time."""

    def __init__(self, root, runner, settings, watch_interval=1.5):
        self.root = Path(root).resolve() if root else None
        self.runner = runner
        self.settings = settings
        self.events = EventBus()
        self.lock = threading.Lock()
        self.host = None
        self.watch_interval = watch_interval
        self.stopping = threading.Event()

    def _fingerprints(self):
        paths = [p for p in self.root.iterdir() if p.is_dir() and library.is_course(p)] if self.root and self.root.is_dir() else []
        host = self.host
        if host and host.workspace not in paths:
            paths.append(host.workspace)
        return {path: library.fingerprint(path) for path in paths}

    def watch(self, seen):
        """Tell open tabs when Codex changes a course or the library from outside the app."""
        while not self.stopping.wait(self.watch_interval):
            current = self._fingerprints()
            if current != seen:
                self.events.publish({'type': 'changed', 'scope': 'library'})
                host = self.host
                if host and current.get(host.workspace) != seen.get(host.workspace):
                    self.events.publish({'type': 'changed', 'scope': 'state'})
                    host._wake_background()
            seen = current

    def open(self, path):
        path = Path(path).resolve()
        with self.lock:
            if self.host and self.host.workspace == path:
                return self.host
            if self.host:
                self.host.close()
                self.host = None
            self.host = Host(path, runner=self.runner, settings=self.settings, events=self.events)
        self.events.publish({'type': 'changed', 'scope': 'course'})
        return self.host

    def open_named(self, name):
        if self.root is None:
            raise OperationError('no_library', 'This host was started for a single course')
        path = library.course_path(self.root, name)
        if not library.is_course(path):
            raise OperationError('unknown_course', f'No course named {name} in {self.root}')
        return self.open(path)

    def require(self):
        host = self.host
        if host is None:
            raise OperationError('no_course', 'Choose a course from the library')
        return host

    def view(self):
        courses = library.list_courses(self.root) if self.root else []
        active = str(self.host.workspace) if self.host else None
        if active and not any(c['path'] == active for c in courses):
            courses.insert(0, library.summary(active))
        return {'root': str(self.root) if self.root else None, 'active': active, 'courses': courses}

    def close(self):
        self.stopping.set()
        with self.lock:
            if self.host:
                self.host.close()


class ActiveHost:
    """Forwards to whichever course is open, so routes need not track course switches."""

    def __init__(self, courses):
        self._courses = courses

    def __getattr__(self, name):
        return getattr(self._courses.require(), name)


def _public_question(branch):
    selected = branch.get('selected_lecture')
    return {**branch, 'selected_lecture': {'id': selected['id']} if selected else None}


def create_app(workspace=None, port=8765, runner=None, settings=None, library_root=None, watch_interval=1.5):
    courses = Courses(library_root, runner, settings or TeacherSettings(), watch_interval)
    if workspace:
        courses.open(workspace)
    host = ActiveHost(courses)
    allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
    origins = {'http://' + h for h in allowed}

    @asynccontextmanager
    async def lifespan(app):
        threading.Thread(target=courses.watch, args=(courses._fingerprints(),), name='library-watch', daemon=True).start()
        try:
            yield
        finally:
            await asyncio.to_thread(courses.close)

    app = FastAPI(title='Throughline', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.courses = courses
    app.state.host = courses.host
    app.state.stop = None

    @app.middleware('http')
    async def guard(request: Request, call_next):
        has_body = request.method in ('POST', 'PUT', 'PATCH', 'DELETE')
        image = request.method == 'POST' and request.url.path == IMAGE_UPLOAD
        if has_body:
            try:
                size = int(request.headers.get('content-length', '0'))
            except ValueError:
                size = -1
            if request.headers.get('transfer-encoding') or size < 0 or size > (MAX_IMAGE if image else MAX_BODY):
                return JSONResponse({'error': 'Request body must have a bounded Content-Length'}, 413)
        origin = request.headers.get('origin')
        if request.headers.get('host') not in allowed or (origin is not None and origin not in origins):
            return JSONResponse({'error': 'Invalid local origin'}, 403)
        # A cross-site page can still send a GET without Origin (an <img>, say); browsers label it with Sec-Fetch-Site.
        site = request.headers.get('sec-fetch-site')
        if request.url.path.startswith('/api/') and site is not None and site not in ('same-origin', 'none'):
            return JSONResponse({'error': 'Invalid local origin'}, 403)
        content_type = request.headers.get('content-type', '').split(';')[0].strip()
        if has_body and size and not (content_type.startswith('image/') if image else content_type == 'application/json'):
            return JSONResponse({'error': 'An image is required' if image else 'JSON required'}, 415)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(OperationError)
    async def operation_error(request, exc):
        status = 415 if exc.code == 'unsupported_image' else 404 if exc.code.startswith('unknown_') else 409
        return JSONResponse({'error': str(exc), 'code': exc.code}, status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        first = exc.errors()[0] if exc.errors() else {}
        field = '.'.join(str(p) for p in first.get('loc', [])[1:])
        return JSONResponse({'error': f"{field}: {first.get('msg', 'invalid request')}" if field else 'Invalid request'}, 400)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        # Anything but an OperationError is a bug: log it, and answer in the shape the interface reads.
        log.error('Unhandled error in %s %s', request.method, request.url.path, exc_info=exc)
        return JSONResponse({'error': f'Internal error ({exc.__class__.__name__}); see the host log', 'code': 'internal_error'}, 500)

    @app.get('/api/state')
    def state():
        current = courses.require()
        snapshot = current.snapshot()
        practice = current.practice.state()
        review = current.review.state(practice)
        # Review questions and their requests live on the review page, not among a section's exercises (ADR 0008).
        # Chapter recaps and quiz questions carry chapter_id; the chapter page lists them, section views leave them out.
        return {**snapshot,
                'questions': [_public_question(b) for b in current.questions.list()],
                'practice': {'tasks': [t for t in practice['tasks'] if t['origin'] != 'review'],
                             'jobs': [j for j in practice['jobs'] if j.get('purpose') != 'review']},
                'review': review,
                'preparation': current.preparation.state(),
                'settings': current.settings.public(),
                'annotations': current.operation({'op': 'annotations.list'})['annotations'],
                'memory': current.operation({'op': 'memory.view'})['entries'],
                'skipped': current.practice.skipped(),
                'builds': current.builds.state()}

    @app.get('/api/events')
    async def events(request: Request):
        subscriber = courses.events.subscribe()

        async def stream():
            try:
                yield 'retry: 1500\n\n'
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(subscriber[1].get(), 15)
                    except asyncio.TimeoutError:
                        yield ': keepalive\n\n'
                        continue
                    yield 'data: ' + json.dumps(event, ensure_ascii=False) + '\n\n'
            finally:
                courses.events.unsubscribe(subscriber)
        return StreamingResponse(stream(), media_type='text/event-stream')

    @app.post('/api/lessons')
    def start_lesson(body: LessonRequest):
        return host.start_lesson(body.model_dump())

    @app.put('/api/preferences')
    def preferences(body: PreferencesRequest):
        return host.set_language(body.language)

    @app.post('/api/turns/{identifier}/pause')
    def pause(identifier: str):
        return {'turn': turn_summary(host.pause_turn(identifier)['turn'])}

    @app.post('/api/turns/{identifier}/resume')
    def resume(identifier: str, body: ResumeRequest):
        result = host.resume_turn(identifier, body.request_id)
        return {**result, 'turn': turn_summary(result['turn'])}

    @app.get('/api/concepts/{concept_id}/preview')
    def preview(concept_id: str):
        return host.navigation.preview(concept_id)

    @app.get('/api/sources/{source_id}/{revision}/{unit_id}')
    def source(source_id: str, revision: str, unit_id: str, format: Optional[str] = None):
        result = host.navigation.source(source_id, revision, unit_id, format)
        if isinstance(result, tuple):
            return Response(result[0], media_type=result[1])
        return result

    @app.post('/api/questions')
    def ask(body: QuestionRequest):
        result = host.questions.ask(body.model_dump(exclude_none=True))
        return {**result, 'turn': turn_summary(result['turn'])}

    @app.post('/api/questions/{identifier}/replies')
    def reply(identifier: str, body: QuestionRequest):
        result = host.questions.reply(identifier, body.model_dump(exclude_none=True))
        return {**result, 'turn': turn_summary(result['turn'])}

    @app.post('/api/questions/{identifier}/choice')
    def choose(identifier: str, body: ChoiceRequest):
        return host.questions.choose(identifier, body.choice)

    @app.post('/api/questions/{identifier}/return')
    def return_to_mainline(identifier: str):
        return host.questions.return_to_mainline(identifier)

    @app.post('/api/annotations')
    def annotate(body: AnnotationRequest):
        result = host.operation({'op': 'annotations.save', 'id': str(uuid.uuid4()), **body.model_dump(exclude_none=True)})
        host.changed()
        return result

    @app.put('/api/annotations/{identifier}')
    def edit_annotation(identifier: str, body: NoteRequest):
        result = host.operation({'op': 'annotations.save', 'id': identifier, 'note': body.note})
        host.changed()
        return result

    @app.delete('/api/annotations/{identifier}')
    def remove_annotation(identifier: str):
        result = host.operation({'op': 'annotations.delete', 'id': identifier})
        host.changed()
        return result

    @app.put('/api/memory/{identifier}')
    def edit_memory(identifier: str, body: MemoryRequest):
        result = host.operation({'op': 'memory.save', 'id': identifier, 'text': body.text})
        host.changed()
        return result

    @app.post('/api/memory/{identifier}/confirm')
    def confirm_memory(identifier: str):
        result = host.operation({'op': 'memory.confirm', 'id': identifier})
        host.changed()
        return result

    @app.delete('/api/memory/{identifier}')
    def remove_memory(identifier: str):
        result = host.operation({'op': 'memory.delete', 'id': identifier})
        host.changed()
        return result

    @app.post('/api/practice/generate')
    def generate(body: GenerateRequest):
        result = host.practice.generate(body.concept_id)
        return {'tasks': result['tasks']} if 'tasks' in result else {**result, 'turn': turn_summary(result['turn'])}

    @app.post(IMAGE_UPLOAD)
    async def upload_image(request: Request):
        data = await request.body()
        return {'image': await asyncio.to_thread(host.practice.save_image, data)}

    @app.get(IMAGE_UPLOAD + '/{name}')
    def answer_image(name: str):
        path, media_type = host.practice.image_file(name)
        return FileResponse(path, media_type=media_type)

    @app.post('/api/practice/tasks/{task_id}/{action}')
    def practice_action(task_id: str, action: str, body: PracticeRequest):
        result = host.practice.act(task_id, action, body.answer, body.question, body.reason, body.images)
        return {**result, 'turn': turn_summary(result['turn'])} if 'turn' in result else result

    @app.get('/api/review')
    def review_schedule():
        return host.review.state()

    @app.post('/api/review/start')
    def start_review(body: ReviewRequest):
        result = host.review.start(body.concept_id)
        return {**result, 'turn': turn_summary(result['turn'])} if 'turn' in result else result

    @app.post('/api/review/postpone')
    def postpone_review(body: ReviewRequest):
        return host.review.postpone(body.concept_id)

    @app.post('/api/sections/next')
    def next_section(body: NextSectionRequest):
        return host.practice.next_section(body.concept_id, body.request_id)

    @app.post('/api/sections/enter')
    def enter_section(body: EnterSectionRequest):
        return host.practice.enter_skipped(body.concept_id, body.request_id)

    @app.post('/api/chapters/{chapter_id}/skip')
    def skip_chapter(chapter_id: str, body: SkipChapterRequest):
        return host.practice.skip_chapter(chapter_id, body.request_id)

    @app.post('/api/chapters/{chapter_id}/build')
    def build_chapter(chapter_id: str):
        return host.builds.request(chapter_id)

    @app.post('/api/chapters/{chapter_id}/recap')
    def recap(chapter_id: str, body: RecapRequest):
        result = host.navigation.start_recap(chapter_id, body.id)
        return {**result, 'turn': turn_summary(result['turn'])}

    @app.post('/api/chapters/{chapter_id}/quiz')
    def chapter_quiz(chapter_id: str):
        result = host.practice.quiz(chapter_id)
        return {**result, 'turn': turn_summary(result['turn'])}

    @app.post('/api/preparation/retry')
    def retry_preparation():
        result = host.preparation.schedule(retry=True)
        host.changed('preparation')
        return {k: v for k, v in result.items() if k != 'turn'}

    @app.get('/api/settings')
    def settings_view():
        return courses.settings.public()

    @app.put('/api/settings')
    def save_settings(body: SettingsRequest):
        result = courses.settings.save(body.model, body.effort, body.small_model, body.service_tier, body.small_effort)
        courses.events.publish({'type': 'changed', 'scope': 'settings'})
        return result

    @app.get('/api/models')
    def models_view():
        try:
            return courses.settings.models()
        except (OSError, RuntimeError) as exc:
            return JSONResponse({'error': str(exc)}, 502)

    @app.get('/api/health')
    def health():
        """A cheap liveness probe for `guided-learning open` and `stop`."""
        return {'pid': os.getpid(), 'launch_id': os.environ.get('GUIDED_LEARNING_LAUNCH_ID')}

    @app.get('/api/library')
    def library_view():
        return courses.view()

    @app.post('/api/library/open')
    def open_course(body: OpenCourseRequest):
        courses.open_named(body.name)
        return courses.view()

    @app.post('/api/shutdown')
    def shutdown():
        if app.state.stop is None:
            return JSONResponse({'error': 'This host cannot be stopped from the interface'}, 409)
        app.state.stop()
        return {'stopping': True}

    if (DIST / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

    @app.get('/')
    def index():
        if not (DIST / 'index.html').is_file():
            return JSONResponse({'error': 'The interface is not built. Run npm run build in web/.'}, 503)
        return FileResponse(DIST / 'index.html')

    @app.get('/favicon.svg')
    def favicon():
        return FileResponse(DIST / 'favicon.svg')

    return app


def serve(workspace=None, port=8765, runner=None, settings=None, on_ready=None, library_root=None):
    """Bind loopback first so port 0 resolves before the host checks Host headers."""
    import uvicorn
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    sock.listen(128)  # connections made right after on_ready wait in the backlog
    actual = sock.getsockname()[1]
    app = create_app(workspace, port=actual, runner=runner, settings=settings, library_root=library_root)
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', timeout_graceful_shutdown=3))
    app.state.stop = lambda: setattr(server, 'should_exit', True)
    if on_ready:
        on_ready(actual)
    server.run(sockets=[sock])
