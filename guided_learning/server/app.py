"""HTTP surface of the learning host. Loopback only; course operations stay the state authority."""
import asyncio
import json
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from ..store import OperationError
from .host import Host, turn_summary

DIST = Path(__file__).resolve().parent.parent / 'web_dist'
MAX_BODY = 1024 * 1024


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


class ChoiceRequest(Body):
    choice: Literal['accept', 'decline']


class GenerateRequest(Body):
    concept_id: str


class PracticeRequest(Body):
    answer: Optional[str] = None


class NextSectionRequest(Body):
    concept_id: str
    request_id: str


class SettingsRequest(Body):
    model: str = ''
    effort: str = 'medium'


def _public_question(branch):
    selected = branch.get('selected_lecture')
    return {**branch, 'selected_lecture': {'id': selected['id']} if selected else None}


def create_app(workspace, port=8765, runner=None, settings=None):
    host = Host(workspace, runner=runner, settings=settings)
    allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
    origins = {'http://' + h for h in allowed}

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await asyncio.to_thread(host.close)

    app = FastAPI(title='Guided Learning', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.host = host

    @app.middleware('http')
    async def guard(request: Request, call_next):
        has_body = request.method in ('POST', 'PUT', 'PATCH', 'DELETE')
        if has_body:
            try:
                size = int(request.headers.get('content-length', '0'))
            except ValueError:
                size = -1
            if request.headers.get('transfer-encoding') or size < 0 or size > MAX_BODY:
                return JSONResponse({'error': 'Request body must have a bounded Content-Length'}, 413)
        origin = request.headers.get('origin')
        if request.headers.get('host') not in allowed or (origin is not None and origin not in origins):
            return JSONResponse({'error': 'Invalid local origin'}, 403)
        if has_body and size and request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
            return JSONResponse({'error': 'JSON required'}, 415)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(OperationError)
    async def operation_error(request, exc):
        return JSONResponse({'error': str(exc), 'code': exc.code}, 409)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        first = exc.errors()[0] if exc.errors() else {}
        field = '.'.join(str(p) for p in first.get('loc', [])[1:])
        return JSONResponse({'error': f"{field}: {first.get('msg', 'invalid request')}" if field else 'Invalid request'}, 400)

    for error in (ValueError, KeyError, TypeError):
        app.add_exception_handler(error, lambda request, exc: JSONResponse({'error': str(exc)}, 400))

    @app.get('/api/state')
    def state():
        snapshot = host.snapshot()
        return {**snapshot,
                'turns': [turn_summary(t) for t in snapshot['turns']],
                'questions': [_public_question(b) for b in host.questions.list()],
                'practice': host.practice.state(),
                'preparation': host.preparation.state(),
                'settings': host.settings.public()}

    @app.get('/api/events')
    async def events(request: Request):
        subscriber = host.events.subscribe()

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
                host.events.unsubscribe(subscriber)
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

    @app.post('/api/questions/{identifier}/choice')
    def choose(identifier: str, body: ChoiceRequest):
        return host.questions.choose(identifier, body.choice)

    @app.post('/api/questions/{identifier}/return')
    def return_to_mainline(identifier: str):
        return host.questions.return_to_mainline(identifier)

    @app.post('/api/practice/generate')
    def generate(body: GenerateRequest):
        result = host.practice.generate(body.concept_id)
        return {'tasks': result['tasks']} if 'tasks' in result else {**result, 'turn': turn_summary(result['turn'])}

    @app.post('/api/practice/tasks/{task_id}/{action}')
    def practice_action(task_id: str, action: str, body: PracticeRequest):
        result = host.practice.act(task_id, action, body.answer)
        return {**result, 'turn': turn_summary(result['turn'])} if 'turn' in result else result

    @app.post('/api/sections/next')
    def next_section(body: NextSectionRequest):
        return host.practice.next_section(body.concept_id, body.request_id)

    @app.post('/api/preparation/retry')
    def retry_preparation():
        result = host.preparation.schedule(retry=True)
        host.changed('preparation')
        return {k: v for k, v in result.items() if k != 'turn'}

    @app.get('/api/settings')
    def settings_view():
        return host.settings.public()

    @app.put('/api/settings')
    def save_settings(body: SettingsRequest):
        result = host.settings.save(body.model, body.effort)
        host.changed('settings')
        return result

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


def serve(workspace, port=8765, runner=None, settings=None, on_ready=None):
    """Bind loopback first so port 0 resolves before the host checks Host headers."""
    import uvicorn
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    sock.listen(128)  # connections made right after on_ready wait in the backlog
    actual = sock.getsockname()[1]
    app = create_app(workspace, port=actual, runner=runner, settings=settings)
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', timeout_graceful_shutdown=3))
    if on_ready:
        on_ready(actual)
    server.run(sockets=[sock])
