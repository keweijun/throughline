"""Studio: course work in the app, as a Codex chat over one long-lived App Server (ADR 0016).

The host keeps no transcript. Codex saves Studio threads in the learner's Codex home; the host only records which
threads belong to which course (`studio.json` beside the teacher settings), forwards the notifications of the
threads it has open to the interface, and holds the approvals and questions Codex is waiting on until the learner
answers them."""
import itertools
import json
import os
import queue
import re
import subprocess
import threading
from pathlib import Path

from ..codex import find_codex
from ..store import OperationError
from .settings import default_path

CLIENT = 'throughline_studio'  # also the threads' originator, which keeps them apart from teaching threads
# Notifications about a thread that the interface draws; moderation, predictions and read state it ignores.
FORWARDED = re.compile(r'^((thread|turn|item)/|error$)')
IGNORED = {'turn/moderationMetadata', 'thread/prediction/updated', 'thread/readState/changed'}
HISTORY = 200  # turns of a thread the interface shows, most recent last
MAX_UPLOAD = 200 * 1024 * 1024
PARAGRAPH = chr(10) * 2
INSTRUCTIONS = PARAGRAPH.join([
    "You are working in Throughline Studio, the Throughline app's own Codex chat for course work. "
    'The learner is in the app{course}. Use the $throughline skill for course work: creating a course, adding files, '
    'building or rebuilding chapters, reviewing pages, changing how a course is taught.',
    'The app is already open, so never run `guided-learning open` or `guided-learning stop`. When a piece of course '
    'work is done, say what changed and name the course; the open app shows the changes by itself. Files the learner '
    "attaches here are already copied into the course's `inputs/` folder: register them where they are.",
    'Studio is a small panel beside the course, so keep replies brief and lead with what the learner has to decide.',
])
LINE = chr(10)


def config_path():
    return default_path().with_name('studio.json')


class StudioError(OperationError):
    pass


class AppServer:
    """One `codex app-server` process. A reader thread routes its replies to the calls waiting on them, and hands
    notifications and Codex's own requests (approvals, questions) to `on_message`."""

    def __init__(self, command, cwd, on_message, on_exit):
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.on_message, self.on_exit = on_message, on_exit
        self.ids = itertools.count(1)
        self.waiting = {}  # request id -> queue for its reply
        self.lock = threading.Lock()
        threading.Thread(target=self._read, name='studio-app-server', daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if 'method' not in message and message.get('id') in self.waiting:
                self.waiting[message['id']].put(message)
            elif 'method' in message:
                try:
                    self.on_message(message)
                except Exception:  # a bad notification must not stop the reader
                    pass
        for reply in list(self.waiting.values()):
            reply.put(None)
        self.on_exit(self)

    def alive(self):
        return self.process.poll() is None

    def _send(self, message):
        with self.lock:
            self.process.stdin.write(json.dumps(message, ensure_ascii=False) + LINE)
            self.process.stdin.flush()

    def call(self, method, params, timeout=30):
        request = next(self.ids)
        reply = self.waiting[request] = queue.Queue()
        try:
            self._send({'id': request, 'method': method, 'params': params})
            message = reply.get(timeout=timeout)
        except (OSError, ValueError) as exc:
            raise StudioError('studio_failed', 'Codex stopped answering') from exc
        except queue.Empty:
            raise StudioError('studio_failed', f'Codex did not answer {method} in time') from None
        finally:
            self.waiting.pop(request, None)
        if message is None:
            raise StudioError('studio_failed', 'Codex closed')
        if 'error' in message:
            error = message['error'] or {}
            code = 'studio_unsupported' if error.get('code') == -32601 else 'studio_failed'
            raise StudioError(code, str(error.get('message') or f'Codex could not {method}'))
        return message.get('result') or {}

    def notify(self, method, params):
        self._send({'method': method, 'params': params})

    def respond(self, request, result):
        self._send({'id': request, 'result': result})

    def refuse(self, request, message):
        self._send({'id': request, 'error': {'code': -32601, 'message': message}})

    def close(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait()


# What Codex may ask the learner while a Studio turn runs, answered from the transcript.
ASKS = {'item/commandExecution/requestApproval', 'item/fileChange/requestApproval',
        'item/permissions/requestApproval', 'item/tool/requestUserInput'}
DECISIONS = {'accept', 'acceptForSession', 'decline', 'cancel'}
# A bogus thread: a Codex with these methods rejects it as unknown, one without them as an unknown method.
PROBE = '00000000-0000-0000-0000-000000000000'
NEEDED = ('thread/turns/list', 'turn/steer')


def _summary(thread, running):
    return {'id': thread['id'], 'name': thread.get('name') or '', 'preview': thread.get('preview') or '',
            'updated_at': thread.get('updatedAt'), 'running': running}


CONTEXT = 'Context from Throughline: '  # how a hand-off's context reaches Codex, and how the transcript finds it again


def message_input(text, elements=(), skills=(), mentions=(), images=(), context=None):
    """The App Server input for one message, as Codex's own composer sends it: the text with the spans its chips
    cover (`elements`, as character offsets, which Codex counts in UTF-8 bytes), then where a hand-off came from
    (`context`, its own text input), the skills and files it names and the images attached to it (local paths)."""
    def byte(offset):
        return len(text[:offset].encode('utf-8'))
    spans = [{'byteRange': {'start': byte(e['start']), 'end': byte(e['end'])}, 'placeholder': text[e['start']:e['end']]}
             for e in elements if 0 <= e['start'] < e['end'] <= len(text)]
    items = [{'type': 'text', 'text': text, 'text_elements': spans}] if text.strip() else []
    if context and context.strip():
        items.append({'type': 'text', 'text': CONTEXT + context.strip(), 'text_elements': []})
    items += [{'type': 'skill', 'name': s['name'], 'path': s['path']} for s in skills]
    items += [{'type': 'mention', 'name': m['name'], 'path': m['path']} for m in mentions]
    items += [{'type': 'localImage', 'path': str(p)} for p in images]
    return items


class Studio:
    """Studio threads of the course library, over one App Server started on first use and again if it exits."""

    def __init__(self, root, events, settings, command=None, path=None):
        self.root = Path(root).resolve() if root else None
        self.events, self.settings = events, settings
        self.command = command
        self.path = Path(path) if path else config_path()
        self.lock = threading.RLock()
        self.server = None
        self.owned = set()  # threads the running App Server has loaded for Studio
        self.active = {}  # thread -> its running turn
        self.ended = {}  # thread -> its last finished turn, which a slow turn/start reply must not mark running again
        self.pending = {}  # request id -> what Codex asked, until the learner answers
        self.missing = None  # why this Codex cannot run Studio, once known
        self.forced = None  # True when Windows has no ready sandbox, so Studio runs with full access

    # Per-user record: Full access, and the threads of each course, newest first.

    def _config(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        courses = data.get('courses') if isinstance(data.get('courses'), dict) else {}
        return {'full_access': data.get('full_access') is True, 'courses': courses}

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
        os.replace(temporary, self.path)

    def _record(self, course, thread, keep=True):
        with self.lock:
            data = self._config()
            ids = [t for t in data['courses'].get(str(course), []) if t != thread]
            data['courses'][str(course)] = [thread, *ids] if keep else ids
            self._save(data)

    def _ids(self, course):
        return self._config()['courses'].get(str(course), [])

    # The App Server.

    def _server(self):
        with self.lock:
            if self.server and self.server.alive():
                return self.server
            if self.missing:
                raise StudioError('studio_unavailable', self.missing)
            command = self.command or [find_codex() or 'codex', 'app-server', '--stdio']
            try:
                server = AppServer(command, self.root or Path.home(), self._message, self._exit)
            except OSError as exc:
                raise StudioError('studio_unavailable', 'Codex CLI not found; install Codex or set CODEX_CLI_PATH') from exc
            try:
                server.call('initialize', {'clientInfo': {'name': CLIENT, 'title': 'Throughline Studio', 'version': '1'},
                                           'capabilities': {'experimentalApi': True}})
                server.notify('initialized', {})
                for method in NEEDED:
                    try:
                        server.call(method, {'threadId': PROBE, 'input': [], 'expectedTurnId': PROBE}, timeout=10)
                    except StudioError as exc:
                        if exc.code == 'studio_unsupported':
                            self.missing = 'Studio needs a newer Codex; update Codex to use it'
                            raise StudioError('studio_unavailable', self.missing) from exc
                if self.forced is None:
                    self.forced = os.name == 'nt' and self._readiness(server) != 'ready'
            except StudioError:
                server.close()
                raise
            self.server = server
            return server

    @staticmethod
    def _readiness(server):
        try:
            return server.call('windowsSandbox/readiness', {}, timeout=10).get('status')
        except StudioError:
            return None

    def _exit(self, server):
        with self.lock:
            if self.server is not server:
                return
            self.server = None
            self.owned.clear()
            self.active.clear()
            self.ended.clear()
            self.pending.clear()
        self.events.publish({'type': 'studio', 'method': 'studio/closed', 'params': {}})

    def _message(self, message):
        method, params = message['method'], message.get('params') or {}
        if 'id' in message:
            if method in ASKS and params.get('threadId') in self.owned:
                entry = {'id': str(message['id']), 'method': method, 'params': params}
                self.pending[entry['id']] = (message['id'], entry)
                self.events.publish({'type': 'studio', 'method': 'studio/request', 'params': entry})
            elif self.server:
                self.server.refuse(message['id'], 'Throughline Studio does not handle this request')
            return
        if method == 'serverRequest/resolved':
            resolved = self.pending.pop(str(params.get('requestId')), None)
            if resolved:
                self.events.publish({'type': 'studio', 'method': 'studio/resolved', 'params': {'id': resolved[1]['id']}})
            return
        thread = params.get('threadId') or (params.get('thread') or {}).get('id')
        if method == 'turn/started':
            self.active[thread] = params['turn']['id']
        elif method == 'turn/completed':
            self.active.pop(thread, None)
            self.ended[thread] = params['turn']['id']
        if method == 'account/rateLimits/updated' or (FORWARDED.match(method) and method not in IGNORED and thread in self.owned):
            self.events.publish({'type': 'studio', 'method': method, 'params': params})

    def close(self):
        with self.lock:
            server, self.server = self.server, None
        if server:
            server.close()

    def ready(self):
        """Start the App Server, checking that this Codex has what Studio needs."""
        self._server()

    # Access (ADR 0016): the library writable without asking, or Full access.

    def access(self):
        saved = self._config()['full_access']
        return {'full_access': saved or bool(self.forced), 'saved': saved, 'forced': bool(self.forced)}

    def checked_access(self):
        """Access as Settings shows it. On Windows, whether Codex's sandbox is ready is only known from Codex, so
        this starts the App Server once if nothing has yet."""
        if os.name == 'nt' and self.forced is None:
            try:
                self._server()
            except StudioError:
                pass
        return self.access()

    def set_full_access(self, on):
        with self.lock:
            data = self._config()
            data['full_access'] = bool(on)
            self._save(data)
        return self.access()

    def _cwd(self, course):
        return self.root or Path(course)

    def _policy(self, course):
        if self.access()['full_access']:
            return {'approvalPolicy': 'never', 'sandboxPolicy': {'type': 'dangerFullAccess'}}
        return {'approvalPolicy': 'on-request', 'sandboxPolicy': {
            'type': 'workspaceWrite', 'writableRoots': [str(self._cwd(course))], 'networkAccess': False,
            'excludeTmpdirEnvVar': False, 'excludeSlashTmp': False}}

    def _thread_settings(self, course):
        current = self.settings.current()
        full = self.access()['full_access']
        params = {'cwd': str(self._cwd(course)), 'approvalPolicy': 'never' if full else 'on-request',
                  'sandbox': 'danger-full-access' if full else 'workspace-write',
                  'config': {'model_reasoning_effort': current['effort']},
                  'developerInstructions': INSTRUCTIONS.format(course=f', with the course in {course} open')}
        if current['model']:
            params['model'] = current['model']
        if current['service_tier']:
            params['serviceTier'] = current['service_tier']
        return params

    # Threads.

    def _owns(self, course, thread):
        if thread not in self._ids(course):
            raise StudioError('unknown_studio_thread', f'No Studio thread {thread} for this course')

    def _load(self, course, thread):
        """Resume a thread in this App Server, so its turns stream here; a loaded thread needs nothing."""
        server = self._server()
        if thread in self.owned:
            return server
        self._owns(course, thread)
        server.call('thread/resume', {**self._thread_settings(course), 'threadId': thread, 'excludeTurns': True})
        self.owned.add(thread)
        return server

    def activity(self, course):
        """The course's threads Codex is working in or waiting on, from what this host saw; never starts Codex, so
        every page can ask."""
        ids = set(self._ids(course))
        return {'running': [t for t in self.active if t in ids],
                'waiting': [entry for _, entry in self.pending.values() if entry['params'].get('threadId') in ids]}

    def threads(self, course):
        ids = self._ids(course)
        if not ids:
            return []
        listed = self._server().call('thread/list', {'cwd': str(self._cwd(course)), 'limit': 100})
        found = {t['id']: t for t in listed.get('data', [])}
        return [_summary(found[t], t in self.active) for t in ids if t in found]

    def history(self, course, thread):
        server = self._load(course, thread)
        page = server.call('thread/turns/list', {'threadId': thread, 'itemsView': 'full', 'sortDirection': 'desc',
                                                 'limit': HISTORY})
        return {'id': thread, 'turns': list(reversed(page.get('data', []))), 'active_turn': self.active.get(thread),
                'pending': [entry for _, entry in self.pending.values() if entry['params'].get('threadId') == thread]}

    def start(self, course):
        server = self._server()
        result = server.call('thread/start', {**self._thread_settings(course), 'ephemeral': False, 'serviceName': CLIENT})
        thread = result['thread']['id']
        self.owned.add(thread)
        self._record(course, thread)
        self.events.publish({'type': 'studio', 'method': 'studio/threads', 'params': {}})
        return thread

    def send(self, course, thread, items):
        """Start a turn with the learner's message, or steer the running one with it, as Codex does."""
        if thread is None:
            thread = self.start(course)
        server = self._load(course, thread)
        running = self.active.get(thread)
        if running:
            try:
                server.call('turn/steer', {'threadId': thread, 'input': items, 'expectedTurnId': running})
                return {'thread': thread, 'turn': running, 'steered': True}
            except StudioError:
                pass  # the turn ended meanwhile: start the next
        current = self.settings.current()
        params = {'threadId': thread, 'input': items, 'effort': current['effort'], **self._policy(course)}
        if current['model']:
            params['model'] = current['model']
        turn = server.call('turn/start', params)['turn']['id']
        if self.ended.get(thread) != turn:
            self.active[thread] = turn
        self._record(course, thread)
        return {'thread': thread, 'turn': turn, 'steered': False}

    def interrupt(self, course, thread):
        server = self._load(course, thread)
        turn = self.active.get(thread)
        if turn:
            server.call('turn/interrupt', {'threadId': thread, 'turnId': turn})
        return {'thread': thread}

    def rename(self, course, thread, name):
        self._load(course, thread).call('thread/name/set', {'threadId': thread, 'name': name.strip()[:120]})
        self.events.publish({'type': 'studio', 'method': 'studio/threads', 'params': {}})
        return {'thread': thread}

    def archive(self, course, thread):
        self._owns(course, thread)
        self._server().call('thread/archive', {'threadId': thread})
        self.owned.discard(thread)
        self._record(course, thread, keep=False)
        self.events.publish({'type': 'studio', 'method': 'studio/threads', 'params': {}})
        return {'thread': thread}

    def answer(self, request, body):
        """Send the learner's answer to an approval or a question Codex is waiting on."""
        with self.lock:
            waiting = self.pending.pop(request, None)
        if not waiting or not self.server:
            raise StudioError('unknown_studio_request', 'Codex is no longer waiting for this answer')
        raw, entry = waiting
        method, params = entry['method'], entry['params']
        if method == 'item/tool/requestUserInput':
            answers = body.get('answers') or {}
            result = {'answers': {str(k): {'answers': [str(a) for a in v]} for k, v in answers.items() if isinstance(v, list)}}
        else:
            decision = body.get('decision')
            if decision not in DECISIONS:
                self.pending[request] = waiting
                raise StudioError('invalid_studio_answer', 'decision must be one of ' + ', '.join(sorted(DECISIONS)))
            if method == 'item/permissions/requestApproval':
                granted = {k: v for k, v in (params.get('permissions') or {}).items() if v is not None}
                result = {'permissions': granted if decision.startswith('accept') else {},
                          'scope': 'session' if decision == 'acceptForSession' else 'turn'}
            else:
                result = {'decision': decision}
        self.server.respond(raw, result)
        self.events.publish({'type': 'studio', 'method': 'studio/resolved', 'params': {'id': request}})
        return {'id': request}

    # The composer: skills for `$`, the course's files for `@`, and files the learner attaches.

    def skills(self, course):
        listed = self._server().call('skills/list', {'cwds': [str(self._cwd(course))]})
        skills = []
        for entry in listed.get('data', []):
            for skill in entry.get('skills', []):
                face = skill.get('interface') or {}
                if skill.get('enabled', True) and not any(s['name'] == skill['name'] for s in skills):
                    skills.append({'name': skill['name'], 'path': skill['path'], 'title': face.get('displayName') or skill['name'],
                                   'description': face.get('shortDescription') or skill.get('shortDescription') or skill.get('description') or ''})
        return skills

    def search(self, course, query):
        found = self._server().call('fuzzyFileSearch', {'query': query, 'roots': [str(course)], 'cancellationToken': None})
        files = []
        for match in found.get('files', []):
            relative = Path(match['path'])
            if relative.parts and (relative.parts[0].startswith('.') or relative.name.startswith('course.sqlite3')):
                continue  # the course database and hidden files are the app's, not material
            files.append({'name': match.get('file_name') or relative.name, 'path': relative.as_posix(),
                          'absolute': str(Path(match.get('root') or course) / relative)})
        return files[:30]

    @staticmethod
    def upload(course, name, chunks):
        """Copy an attached file into the course's `inputs/` folder, where the skill registers sources from."""
        name = Path(str(name or '').replace(chr(0), '')).name.strip()
        if not name or name.startswith('.'):
            raise StudioError('invalid_studio_file', 'The file needs a name')
        folder = Path(course) / 'inputs'
        folder.mkdir(parents=True, exist_ok=True)
        target, stem, suffix = folder / name, Path(name).stem, Path(name).suffix
        for n in itertools.count(2):
            if not target.exists():
                break
            target = folder / f'{stem} ({n}){suffix}'
        size = 0
        try:
            with target.open('xb') as out:
                for chunk in chunks:
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise StudioError('invalid_studio_file', 'Files larger than 200 MB cannot be attached')
                    out.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return {'name': target.name, 'path': target.relative_to(course).as_posix(), 'absolute': str(target)}
