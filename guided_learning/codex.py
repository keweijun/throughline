"""Owned Codex App Server transport. Never writes teacher-generated lecture files."""
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path


def find_codex():
    """The codex binary: CODEX_CLI_PATH, then PATH, then the copy bundled with the Codex desktop app."""
    if os.environ.get('CODEX_CLI_PATH'):
        return os.environ['CODEX_CLI_PATH']
    found = shutil.which('codex')
    if found:
        return found
    bundled = ['/Applications/Codex.app/Contents/Resources/codex', os.path.expanduser('~/Applications/Codex.app/Contents/Resources/codex')]
    if os.environ.get('LOCALAPPDATA'):
        # The Windows app unpacks its CLI into a per-version folder; prefer the newest.
        windows = Path(os.environ['LOCALAPPDATA']) / 'OpenAI' / 'Codex' / 'bin'
        bundled += sorted((str(p) for p in windows.glob('*/codex.exe')), key=os.path.getmtime, reverse=True)
        bundled.append(str(windows / 'codex.exe'))
    return next((path for path in bundled if os.path.isfile(path)), None)


def _message(error):
    """The human-readable text of a JSON-RPC or turn error, if Codex sent one."""
    if isinstance(error, dict):
        return str(error.get('message') or error.get('error') or '').strip()
    return str(error or '').strip()


def _explain(summary, detail):
    return f'{summary}: {detail}' if detail else summary


def list_models(command=None, timeout=20):
    """The models the signed-in Codex account can use, from the App Server's paginated model/list."""
    command = command or [find_codex() or 'codex','app-server','--stdio']
    try:
        process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                   text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except OSError as exc:
        raise RuntimeError('Codex CLI not found; install Codex or set CODEX_CLI_PATH') from exc
    incoming = queue.Queue()
    def reader():
        for line in process.stdout:
            try: incoming.put(json.loads(line))
            except json.JSONDecodeError: continue
        incoming.put(None)
    threading.Thread(target=reader,daemon=True).start()
    def send(value):
        process.stdin.write(json.dumps(value)+'\n')
        process.stdin.flush()
    models, request = [], 1
    deadline = time.monotonic()+timeout
    try:
        send({'id':request,'method':'initialize','params':{'clientInfo':{'name':'guided_learning','version':'0.2.0'},'capabilities':{'experimentalApi':True}}})
        while time.monotonic() < deadline:
            try: event = incoming.get(timeout=.1)
            except queue.Empty: continue
            if event is None:
                raise RuntimeError('Codex closed before listing models')
            if event.get('id') != request or 'method' in event: continue
            if 'error' in event:
                raise RuntimeError(_explain('Codex could not list models; check CLI authentication', _message(event['error'])))
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
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=2)
        except (OSError,subprocess.TimeoutExpired):
            process.kill(); process.wait()
        process.stdout.close()


def _tidy(command, cwd, delete=(), sweep_before=None, timeout=20):
    """Delete saved threads, and with `sweep_before` (a Unix time) also the empty teaching threads this app left in
    `cwd` before then, say after a crash. Best effort: Codex may be gone or busy."""
    try:
        process = subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                   text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
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
            listed = call(2,'thread/list',{'cwd':str(cwd),'limit':100}) or {}
            ids += [t['id'] for t in listed.get('data',[]) if t.get('originator') == 'guided_learning' and not t.get('ephemeral')
                    and (t.get('createdAt') or 0) < sweep_before and t['id'] not in ids]
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
    Every turn is reverted when it ends, so a thread lent out carries no history (ADR 0002). Idle threads are deleted
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
            _tidy(command or [find_codex() or 'codex','app-server','--stdio'], cwd, ids, timeout=5)


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
        command = self.command or [find_codex() or 'codex','app-server','--stdio']
        # A teaching prompt's instructions go into a saved thread lent for this turn, so the prompt cache can reuse them.
        instructions = getattr(prompt, 'instructions', None)
        text = prompt.request if instructions is not None else prompt
        pooled = instructions is not None and THREADS.enabled
        key = (str(cwd), self.model, self.service_tier)
        saved = THREADS.take(key, command) if pooled else None
        process = subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                   text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        incoming = queue.Queue()
        def reader():
            for line in process.stdout:
                try: incoming.put(json.loads(line))
                except json.JSONDecodeError: continue
            incoming.put(None)
        threading.Thread(target=reader,daemon=True).start()
        def send(value):
            process.stdin.write(json.dumps(value,ensure_ascii=False)+'\n')
            process.stdin.flush()
        thread_id = turn_id = None
        phases, chunks, finals = {}, {}, {}
        usage = {}
        order = []
        interrupted_at = None
        started = last_heard = time.monotonic()
        last_error = ''
        settled = False
        def settle():
            """Revert the finished turn so the thread can be lent again, or have it deleted."""
            send({'id':5,'method':'thread/revert','params':{'threadId':thread_id,'beforeTurnId':turn_id}})
            deadline = time.monotonic()+10
            while time.monotonic() < deadline:
                try: event = incoming.get(timeout=.1)
                except queue.Empty: continue
                if event is None: break
                if event.get('id') == 5 and 'method' not in event:
                    if 'result' in event:
                        return THREADS.give(key, thread_id, command)
                    if (event.get('error') or {}).get('code') == -32601:
                        THREADS.enabled = False  # this Codex cannot revert: lend no more threads
                    break
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
                    raise RuntimeError(_explain('Model connection closed before completion', last_error))
                if event.get('error') and event.get('id') == 2 and saved:
                    THREADS.drop(key, saved, command)  # gone or unusable: start another
                    saved = None
                    send({'id':2,'method':'thread/start','params':{**thread,'ephemeral':False}})
                    continue
                if event.get('error') and event.get('id') in (1,2,3):
                    raise RuntimeError(_explain('Codex rejected initialization or generation; check CLI authentication and model configuration', _message(event['error'])))
                if event.get('id') == 1 and 'result' in event:
                    send({'method':'initialized','params':{}})
                    thread = {'cwd':str(cwd),'approvalPolicy':'never','sandbox':'read-only','config':{'model_reasoning_effort':self.effort}}
                    if self.model: thread['model'] = self.model
                    if self.service_tier: thread['serviceTier'] = self.service_tier
                    if instructions is not None: thread['developerInstructions'] = instructions
                    if saved:
                        send({'id':2,'method':'thread/resume','params':{**thread,'threadId':saved,'excludeTurns':True}})
                    else:
                        send({'id':2,'method':'thread/start','params':{**thread,'ephemeral':not pooled}})
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
                if method == 'error':
                    last_error = _message(params.get('error')) or last_error
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
                        raise RuntimeError(_explain('Model turn did not complete successfully', _message(params['turn'].get('error')) or last_error))
                    if not any(phases.get(k)=='final_answer' for k in finals):
                        raise RuntimeError('Model finished without an authoritative final answer')
                    emit({'kind':'complete','usage':usage} if usage else {'kind':'complete'})
                    if pooled:
                        settled = True
                        settle()
                    return
            raise TimeoutError('Model generation exceeded time limit')
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
