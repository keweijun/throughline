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


class CodexRunner:
    def __init__(self, model=None, effort='medium', command=None, timeout=600, ephemeral=True, project_id=None, name=None):
        self.model, self.effort, self.timeout = model, effort, timeout
        self.command = command
        # A kept thread is saved like any Codex chat, so the Codex app can open it.
        self.ephemeral = ephemeral
        self.project_id = project_id
        self.name = name

    def run(self, prompt, cwd, emit, cancel):
        command = self.command or [find_codex() or 'codex','app-server','--stdio']
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
        order = []
        interrupted_at = None
        started = time.monotonic()
        try:
            send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'guided_learning','version':'0.2.0'},'capabilities':{'experimentalApi':True}}})
            while time.monotonic()-started < self.timeout:
                if cancel.is_set() and interrupted_at is None:
                    if not (thread_id and turn_id): return
                    send({'id':4,'method':'turn/interrupt','params':{'threadId':thread_id,'turnId':turn_id}})
                    interrupted_at = time.monotonic()
                if interrupted_at and time.monotonic()-interrupted_at > 10:
                    return
                try: event = incoming.get(timeout=.1)
                except queue.Empty: continue
                if event is None:
                    raise RuntimeError('Model connection closed before completion')
                if event.get('error') and event.get('id') in (1,2,3):
                    raise RuntimeError('Codex rejected initialization or generation; check CLI authentication and model configuration')
                if event.get('id') == 1 and 'result' in event:
                    send({'method':'initialized','params':{}})
                    params = {'cwd':str(cwd),'ephemeral':self.ephemeral,'approvalPolicy':'never','sandbox':'read-only',
                              'config':{'model_reasoning_effort':self.effort}}
                    if self.model: params['model'] = self.model
                    if self.project_id: params['projectId'] = self.project_id
                    send({'id':2,'method':'thread/start','params':params})
                elif event.get('id') == 2 and 'result' in event:
                    thread_id = event['result']['thread']['id']
                    if not self.ephemeral: emit({'kind':'thread','id':thread_id})
                    if self.name: send({'id':5,'method':'thread/name/set','params':{'threadId':thread_id,'name':self.name}})
                    params = {'threadId':thread_id,'effort':self.effort,'input':[{'type':'text','text':prompt}]}
                    if self.model: params['model'] = self.model
                    if cancel.is_set(): return
                    send({'id':3,'method':'turn/start','params':params})
                elif event.get('id') == 3 and 'result' in event:
                    turn_id = event['result']['turn']['id']
                method, params = event.get('method'), event.get('params',{})
                if 'id' in event and method:
                    send({'id':event['id'],'error':{'code':-32601,'message':'Interactive tool requests are unavailable'}})
                if params.get('threadId',thread_id) != thread_id: continue
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
                if method == 'item/agentMessage/delta':
                    iid = params['itemId']; text = params.get('delta','')
                    chunks[iid] = chunks.get(iid,'') + text
                    if phases.get(iid) in ('partial_answer','final_answer') and not cancel.is_set():
                        emit({'kind':'delta','text':text})
                if method == 'turn/completed':
                    if cancel.is_set(): return
                    if params['turn'].get('status') != 'completed':
                        raise RuntimeError('Model turn did not complete successfully')
                    if not any(phases.get(k)=='final_answer' for k in finals):
                        raise RuntimeError('Model finished without an authoritative final answer')
                    emit({'kind':'complete'})
                    return
            raise TimeoutError('Model generation exceeded time limit')
        finally:
            try:
                if cancel.is_set() and process.poll() is None: process.terminate()
                process.stdin.close()
                process.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
            process.stdout.close()
