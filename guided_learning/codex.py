"""Owned Codex App Server transport. Never writes teacher-generated lecture files."""
import json
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .logs import Tail

log = logging.getLogger(__name__)
NOT_FOUND = ('Codex was not found. Install Codex (the codex command or the Codex app), or set CODEX_CLI_PATH to where it '
             'is, then try again.')


def _explicit_or_on_path():
    """The codex binary named by CODEX_CLI_PATH, else the one on PATH, as an absolute path when it can be resolved."""
    named = os.environ.get('CODEX_CLI_PATH')
    if named:
        return shutil.which(named) or named
    return shutil.which('codex')


def _settings_path():
    from .server.settings import default_path  # imported here: the settings module imports this one
    return default_path()


def _usable(path):
    return isinstance(path, str) and os.path.isabs(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def _saved():
    """What setup recorded about codex in the per-user settings: its path, and the folders it needs on PATH to run."""
    try:
        data = json.loads(_settings_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None, []
    if not isinstance(data, dict):
        return None, []
    path, folders = data.get('codex_path'), data.get('codex_path_dirs')
    folders = [f for f in folders if isinstance(f, str) and os.path.isabs(f)] if isinstance(folders, list) else []
    return path if _usable(path) else None, folders


def saved_codex():
    """The codex binary setup found, saved in the per-user settings, while it is still there and executable."""
    return _saved()[0]


def _runs_on_node(path):
    """True when `path` is an npm-installed codex: a Node script, or npm's Windows shim that starts one."""
    real = os.path.realpath(path)
    if 'node_modules' in Path(real).parts:
        return True
    try:
        with open(real, 'rb') as file:
            head = file.read(4096)
    except OSError:
        return False
    if head.startswith(b'#!'):
        return b'node' in head.split(b'\n', 1)[0]
    return Path(real).suffix.lower() in ('.cmd', '.bat', '.ps1') and b'node' in head.lower()


def remember_codex():
    """Save where setup found codex (CODEX_CLI_PATH or PATH), so a host started without that PATH, from Finder,
    Spotlight or an app menu, still finds it. An npm-installed codex is a Node script, so the folder of the `node` this
    PATH has is saved with it, for the launcher's PATH may lack it too. Returns the saved path, or None when there was
    nothing to save."""
    found = _explicit_or_on_path()
    if not found:
        return None
    found = os.path.abspath(found)
    if not _usable(found):
        return None
    node = shutil.which('node') if _runs_on_node(found) else None
    folders = [os.path.dirname(os.path.abspath(node))] if node else []
    from .userfiles import write_json
    try:
        write_json(_settings_path(), {'codex_path': found, 'codex_path_dirs': folders})
    except OSError:
        return None
    return found


def find_codex():
    """The codex binary: CODEX_CLI_PATH, then PATH, then where setup last found it, then the copy bundled with the
    Codex desktop app. The host's own PATH is never changed, so a codex setup saves later is found without a restart."""
    found = _explicit_or_on_path()
    if found:
        return found
    saved = saved_codex()
    if saved:
        return saved
    bundled = ['/Applications/Codex.app/Contents/Resources/codex', os.path.expanduser('~/Applications/Codex.app/Contents/Resources/codex')]
    if os.environ.get('LOCALAPPDATA'):
        # The Windows app unpacks its CLI into a per-version folder; prefer the newest.
        windows = Path(os.environ['LOCALAPPDATA']) / 'OpenAI' / 'Codex' / 'bin'
        bundled += sorted((str(p) for p in windows.glob('*/codex.exe')), key=os.path.getmtime, reverse=True)
        bundled.append(str(windows / 'codex.exe'))
    return next((path for path in bundled if os.path.isfile(path)), None)


def codex_env(executable):
    """The environment for a Codex process started from `executable`: None (the host's own) unless it is the codex
    setup saved, whose folder and the folders setup recorded for it (its `node`) are added to that process's PATH
    only, since the launcher's PATH may have neither. Every Codex process Throughline starts gets its environment
    from here."""
    saved, folders = _saved()
    if not saved or not executable or os.path.normcase(os.path.abspath(executable)) != os.path.normcase(saved):
        return None
    path = os.environ.get('PATH', '')
    have = {os.path.normcase(p) for p in path.split(os.pathsep) if p}
    extra = []
    for folder in [os.path.dirname(saved), *folders]:
        if os.path.normcase(folder) not in have:
            have.add(os.path.normcase(folder))
            extra.append(folder)
    return {**os.environ, 'PATH': os.pathsep.join(filter(None, [path, *extra]))} if extra else None


def app_server():
    """The command that starts Codex's App Server."""
    return [find_codex() or 'codex', 'app-server', '--stdio']


def _message(error):
    """The human-readable text of a JSON-RPC or turn error, if Codex sent one."""
    if isinstance(error, dict):
        return str(error.get('message') or error.get('error') or '').strip()
    return str(error or '').strip()


def _explain(summary, detail):
    return f'{summary}: {detail}' if detail else summary


# What a learner can do about a turn Codex refused, by the reason it gives (`codexErrorInfo` of a TurnError).
ADVICE = {
    'usageLimitExceeded': 'Your Codex usage limit is reached. Lessons continue once it resets; Codex shows when.',
    'sessionBudgetExceeded': 'Your Codex usage limit is reached. Lessons continue once it resets; Codex shows when.',
    'rateLimitExceeded': 'Codex is getting too many requests right now. Try again in a minute.',
    'serverOverloaded': 'Codex is busy right now. Try again in a minute.',
    'unauthorized': 'Codex is not signed in. Sign in in the Codex app, or run "codex login", then try again.',
    'modelNotFound': 'Your Codex account cannot use the chosen model. Choose another one in Settings.',
}


def _advice(error):
    """A sentence on what to do about a Codex error, or '' when Codex gave no known reason."""
    info = error.get('codexErrorInfo') if isinstance(error, dict) else None
    if isinstance(info, dict) and set(info) & {'httpConnectionFailed', 'responseStreamConnectionFailed'}:
        return 'Codex could not reach OpenAI. Check your internet connection, then try again.'
    return ADVICE.get(info, '') if isinstance(info, str) else ''


def _failed(summary, error, fallback=''):
    """The error a failed turn reports: advice the learner can act on first, then what Codex said."""
    detail = _message(error) or fallback
    advice = _advice(error)
    return f'{advice} ({detail})' if advice and detail else advice or _explain(summary, detail)


def _start(command, **options):
    """Start Codex's App Server, keeping the end of what it writes to stderr for the log."""
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8', errors='replace', env=codex_env(command[0]),
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), **options)
    except OSError as exc:
        raise RuntimeError(NOT_FOUND) from exc
    return process, Tail(process.stderr)


def list_models(command=None, timeout=20):
    """The models the signed-in Codex account can use, from the App Server's paginated model/list."""
    command = command or app_server()
    process, tail = _start(command)
    incoming = queue.Queue()
    def reader():
        for line in process.stdout:
            try: incoming.put(json.loads(line))
            except json.JSONDecodeError: continue
        incoming.put(None)
    threading.Thread(target=reader,daemon=True).start()
    def send(value):
        try:
            process.stdin.write(json.dumps(value)+'\n')
            process.stdin.flush()
        except OSError:
            pass  # Codex has exited; the reader reports the closed connection with what Codex wrote
    models, request = [], 1
    deadline = time.monotonic()+timeout
    try:
        send({'id':request,'method':'initialize','params':{'clientInfo':{'name':'guided_learning','version':'0.2.0'},'capabilities':{'experimentalApi':True}}})
        while time.monotonic() < deadline:
            try: event = incoming.get(timeout=.1)
            except queue.Empty: continue
            if event is None:
                raise RuntimeError(_explain('Codex closed before listing models', (tail.text().splitlines() or [''])[-1]))
            if event.get('id') != request or 'method' in event: continue
            if 'error' in event:
                raise RuntimeError(_failed('Codex could not list models; check CLI authentication', event['error']))
            result = event.get('result') or {}
            if request == 1:
                send({'method':'initialized','params':{}})
            else:
                models += [{'id':m['id'],'name':m.get('displayName') or m['id'],'description':m.get('description') or '',
                            'default':bool(m.get('isDefault')),
                            'tiers':[{'id':t['id'],'name':t.get('name') or t['id'],'description':t.get('description') or ''}
                                     for t in m.get('serviceTiers') or []],
                            'efforts':[e['reasoningEffort'] for e in m.get('supportedReasoningEfforts') or []]}
                           for m in result.get('data',[]) if not m.get('hidden')]
                if not result.get('nextCursor'):
                    return models
            request += 1
            send({'id':request,'method':'model/list','params':{'cursor':result['nextCursor']} if result.get('nextCursor') else {}})
        raise TimeoutError('Codex took too long to list models')
    except Exception as exc:
        tail.log(log, f'Listing models failed ({exc})')
        raise
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=2)
        except (OSError,subprocess.TimeoutExpired):
            process.kill(); process.wait()
        process.stdout.close()
        process.stderr.close()


def _tidy(command, cwd, delete=(), sweep_before=None, timeout=20):
    """Delete saved threads, and with `sweep_before` (a Unix time) also the empty teaching threads this app left in
    `cwd` before then, say after a crash. Best effort: Codex may be gone or busy."""
    try:
        process = subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                   text=True,encoding='utf-8',errors='replace',env=codex_env(command[0]),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except OSError:
        return
    incoming = queue.Queue()
    def reader():
        for line in process.stdout:
            try: incoming.put(json.loads(line))
            except json.JSONDecodeError: continue
        incoming.put(None)
    threading.Thread(target=reader,daemon=True).start()
    deadline = time.monotonic()+timeout
    def call(request, method, params):
        process.stdin.write(json.dumps({'id':request,'method':method,'params':params})+'\n'); process.stdin.flush()
        while time.monotonic() < deadline:
            try: event = incoming.get(timeout=.1)
            except queue.Empty: continue
            if event is None: raise OSError('Codex closed')
            if event.get('id') == request and 'method' not in event: return event.get('result')
        raise OSError('Codex did not answer')
    try:
        call(1,'initialize',{'clientInfo':{'name':'guided_learning','version':'0.2.0'},'capabilities':{'experimentalApi':True}})
        process.stdin.write(json.dumps({'method':'initialized','params':{}})+'\n'); process.stdin.flush()
        ids = list(delete)
        if sweep_before is not None:
            for n, archived in enumerate((False, True)):  # idle threads are archived; one a crash interrupted is not
                listed = call(2+n,'thread/list',{'cwd':str(cwd),'limit':100,'archived':archived}) or {}
                for t in listed.get('data',[]):
                    if t.get('originator') == 'guided_learning' and not t.get('ephemeral') \
                            and (t.get('createdAt') or 0) < sweep_before and t['id'] not in ids:
                        ids.append(t['id'])
        for n, thread in enumerate(ids):
            call(10+n,'thread/delete',{'threadId':thread})
    except (OSError,ValueError,KeyError,TypeError):
        pass
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=2)
        except (OSError,subprocess.TimeoutExpired):
            process.kill(); process.wait()
        process.stdout.close()


class SavedThreads:
    """Saved Codex threads for teaching turns, kept per course folder, model and service tier. The model's prompt
    cache is keyed by thread, so turns that reuse a thread reuse the cached developer instructions of the turn before.
    Every turn is reverted when it ends, so a thread lent out carries no history (ADR 0002), and archived, so idle
    threads stay out of the learner's Codex session list. Idle threads are deleted
    once the cache has expired, beyond a few per key, and when the course closes; a restarted host deletes those a
    crash left behind."""
    IDLE = 900  # seconds; longer than the cache keeps a prefix
    SPARE = 3

    def __init__(self):
        self.lock = threading.Lock()
        self.idle = {}  # (cwd, model, tier) -> [(thread id, released at)]
        self.swept = set()
        self.enabled = True
        self.started = time.time()

    def _later(self, command, cwd, delete=(), sweep=False):
        if delete or sweep:
            threading.Thread(target=_tidy,args=(command,cwd,list(delete),self.started if sweep else None),daemon=True).start()

    def take(self, key, command):
        """A thread to resume for `key`, or None to start one."""
        with self.lock:
            sweep = key[0] not in self.swept
            self.swept.add(key[0])
            now = time.time()
            fresh = [(t, at) for t, at in self.idle.get(key, []) if now-at < self.IDLE]
            stale = [t for t, at in self.idle.get(key, []) if now-at >= self.IDLE]
            thread = fresh.pop()[0] if fresh else None
            self.idle[key] = fresh
        self._later(command, key[0], stale, sweep)
        return thread

    def give(self, key, thread, command):
        with self.lock:
            spare = self.idle.setdefault(key, [])
            spare.append((thread, time.time()))
            extra = [t for t, _ in spare[:-self.SPARE]]
            del spare[:-self.SPARE]
        self._later(command, key[0], extra)

    def drop(self, key, thread, command):
        """Delete a thread that cannot be lent again (its turn failed or was not reverted)."""
        self._later(command, key[0], [thread])

    def close(self, cwd, command=None):
        """Delete the idle threads of a course folder, waiting briefly: the course is closing."""
        with self.lock:
            keys = [k for k in self.idle if k[0] == str(cwd)]
            ids = [t for k in keys for t, _ in self.idle.pop(k)]
        if ids:
            _tidy(command or app_server(), cwd, ids, timeout=5)


THREADS = SavedThreads()
class CodexRunner:
    """One Codex thread per turn: a saved thread lent from THREADS for a teaching prompt, otherwise an ephemeral one.
    A turn fails when Codex stays silent for `idle_timeout` seconds,
    or, however lively, runs past the `timeout` cap. `images` are paths of local image files sent with the prompt."""

    def __init__(self, model=None, effort='medium', command=None, timeout=3600, idle_timeout=300, service_tier=None):
        self.model, self.effort, self.timeout, self.idle_timeout = model, effort, timeout, idle_timeout
        self.service_tier = service_tier
        self.command = command

    def run(self, prompt, cwd, emit, cancel, images=()):
        command = self.command or app_server()
        # A teaching prompt's instructions go into a saved thread lent for this turn, so the prompt cache can reuse them.
        instructions = getattr(prompt, 'instructions', None)
        text = prompt.request if instructions is not None else prompt
        pooled = instructions is not None and THREADS.enabled
        key = (str(cwd), self.model, self.service_tier)
        saved = THREADS.take(key, command) if pooled else None
        process, tail = _start(command, cwd=cwd)
        incoming = queue.Queue()
        def reader():
            for line in process.stdout:
                try: incoming.put(json.loads(line))
                except json.JSONDecodeError: continue
            incoming.put(None)
        threading.Thread(target=reader,daemon=True).start()
        def send(value):
            try:
                process.stdin.write(json.dumps(value,ensure_ascii=False)+'\n')
                process.stdin.flush()
            except OSError:
                pass  # Codex has exited (not signed in, say); the reader reports it with what Codex wrote
        thread_id = turn_id = None
        phases, chunks, finals = {}, {}, {}
        usage = {}
        order = []
        interrupted_at = None
        started = last_heard = time.monotonic()
        last_error = {}
        settled = False
        def settle():
            """Revert the finished turn and archive the thread, which keeps it out of the learner's Codex session list,
            so it can be lent again; or have it deleted."""
            send({'id':5,'method':'thread/revert','params':{'threadId':thread_id,'beforeTurnId':turn_id}})
            deadline = time.monotonic()+10
            while time.monotonic() < deadline:
                try: event = incoming.get(timeout=.1)
                except queue.Empty: continue
                if event is None: break
                if event.get('id') == 5 and 'method' not in event:
                    if 'result' in event:
                        send({'id':7,'method':'thread/archive','params':{'threadId':thread_id}})
                        continue
                    if (event.get('error') or {}).get('code') == -32601:
                        THREADS.enabled = False  # this Codex cannot revert: lend no more threads
                    break
                if event.get('id') == 7 and 'method' not in event:
                    return THREADS.give(key, thread_id, command)  # an unarchived thread is still lent, only listed
            THREADS.drop(key, thread_id, command)
        try:
            send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'guided_learning','version':'0.2.0'},'capabilities':{'experimentalApi':True}}})
            while time.monotonic()-started < self.timeout:
                if time.monotonic()-last_heard > self.idle_timeout:
                    raise TimeoutError(f'Codex sent nothing for {self.idle_timeout} seconds')
                if cancel.is_set() and interrupted_at is None:
                    if not (thread_id and turn_id): return
                    send({'id':4,'method':'turn/interrupt','params':{'threadId':thread_id,'turnId':turn_id}})
                    interrupted_at = time.monotonic()
                if interrupted_at and time.monotonic()-interrupted_at > 10:
                    return
                try: event = incoming.get(timeout=.1)
                except queue.Empty: continue
                last_heard = time.monotonic()
                if event is None:
                    raise RuntimeError(_failed('Model connection closed before completion', last_error, (tail.text().splitlines() or [''])[-1]))
                if event.get('error') and event.get('id') == 2 and saved:
                    THREADS.drop(key, saved, command)  # gone or unusable: start another
                    saved = None
                    send({'id':2,'method':'thread/start','params':{**thread,'ephemeral':False}})
                    continue
                if event.get('error') and event.get('id') in (1,2,3):
                    raise RuntimeError(_failed('Codex rejected initialization or generation; check CLI authentication and model configuration', event['error']))
                if event.get('id') == 1 and 'result' in event:
                    send({'method':'initialized','params':{}})
                    thread = {'cwd':str(cwd),'approvalPolicy':'never','sandbox':'read-only','config':{'model_reasoning_effort':self.effort}}
                    if self.model: thread['model'] = self.model
                    if self.service_tier: thread['serviceTier'] = self.service_tier
                    if instructions is not None: thread['developerInstructions'] = instructions
                    if saved:
                        # An idle thread is archived, and Codex resumes only unarchived ones.
                        send({'id':6,'method':'thread/unarchive','params':{'threadId':saved}})
                    else:
                        send({'id':2,'method':'thread/start','params':{**thread,'ephemeral':not pooled}})
                elif event.get('id') == 6 and 'method' not in event:
                    send({'id':2,'method':'thread/resume','params':{**thread,'threadId':saved,'excludeTurns':True}})
                elif event.get('id') == 2 and 'result' in event:
                    thread_id = event['result']['thread']['id']
                    params = {'threadId':thread_id,'effort':self.effort,'input':[{'type':'text','text':text}]+[{'type':'localImage','path':str(p)} for p in images]}
                    if self.model: params['model'] = self.model
                    if cancel.is_set(): return
                    send({'id':3,'method':'turn/start','params':params})
                elif event.get('id') == 3 and 'result' in event:
                    turn_id = event['result']['turn']['id']
                method, params = event.get('method'), event.get('params',{})
                if 'id' in event and method:
                    send({'id':event['id'],'error':{'code':-32601,'message':'Interactive tool requests are unavailable'}})
                if params.get('threadId',thread_id) != thread_id: continue
                if method == 'error' and _message(params.get('error')):
                    last_error = params['error']
                if method == 'turn/started': turn_id = params['turn']['id']
                if params.get('turnId',turn_id) != turn_id: continue
                if method in ('item/started','item/completed'):
                    item = params['item']
                    if item.get('type') == 'agentMessage':
                        iid = item['id']
                        if iid not in order: order.append(iid)
                        phases[iid] = item.get('phase')
                        if method == 'item/completed' and phases[iid] in ('partial_answer','final_answer'):
                            finals[iid] = item.get('text','')
                            if phases[iid] == 'final_answer':
                                emit({'kind':'final','text':'\n\n'.join(finals[k] for k in order if k in finals)})
                if method == 'thread/tokenUsage/updated':
                    # One update per model request; `last` is that request, so a turn's usage is their sum.
                    for name, value in params['tokenUsage']['last'].items():
                        if isinstance(value, int): usage[name] = usage.get(name, 0) + value
                if method == 'item/agentMessage/delta':
                    iid = params['itemId']; text = params.get('delta','')
                    chunks[iid] = chunks.get(iid,'') + text
                    if phases.get(iid) in ('partial_answer','final_answer') and not cancel.is_set():
                        emit({'kind':'delta','text':text})
                if method == 'turn/completed':
                    if cancel.is_set(): return
                    if params['turn'].get('status') != 'completed':
                        raise RuntimeError(_failed('Model turn did not complete successfully', params['turn'].get('error') or last_error))
                    if not any(phases.get(k)=='final_answer' for k in finals):
                        raise RuntimeError('Model finished without an authoritative final answer')
                    emit({'kind':'complete','usage':usage} if usage else {'kind':'complete'})
                    if pooled:
                        settled = True
                        settle()
                    return
            raise TimeoutError('Model generation exceeded time limit')
        except Exception as exc:
            tail.log(log, f'A teaching turn failed ({exc})')
            raise
        finally:
            if pooled and thread_id and not settled:
                THREADS.drop(key, thread_id, command)
            try:
                if cancel.is_set() and process.poll() is None: process.terminate()
                process.stdin.close()
                process.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
            process.stdout.close()
            process.stderr.close()
