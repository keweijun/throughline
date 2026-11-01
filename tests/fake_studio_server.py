"""A scripted `codex app-server` for Studio tests: `python fake_studio_server.py <log> [old]`.

It logs every message it receives to <log> as JSON lines. A turn's text picks its script: "approve" asks to run a
command and replies with the learner's decision, "ask" asks a question and replies with the answer, "wait" keeps
running until it is steered or interrupted; anything else replies "done". With `old` it lacks `turn/steer`, as an
older Codex would."""
import json
import sys
import time

log = open(sys.argv[1], 'a', encoding='utf-8')
old = len(sys.argv) > 2 and sys.argv[2] == 'old'
threads, turns = {}, {}
waiting = {}  # server request id -> (thread, turn, kind)
asked = iter(range(900, 10000))
LINE = chr(10)


def send(message):
    sys.stdout.write(json.dumps(message) + LINE)
    sys.stdout.flush()


def note(method, params):
    send({'method': method, 'params': params})


def thread(tid, **extra):
    return {'id': tid, 'name': None, 'preview': '', 'createdAt': 1, 'updatedAt': int(time.time()), 'status': {'type': 'idle'},
            'turns': [], **threads.get(tid, {}), **extra}


def message(tid, turn, text, item='m'):
    entry = {'type': 'agentMessage', 'id': f'{turn}-{item}', 'text': '', 'phase': 'final_answer'}
    note('item/started', {'threadId': tid, 'turnId': turn, 'item': entry})
    note('item/agentMessage/delta', {'threadId': tid, 'turnId': turn, 'itemId': entry['id'], 'delta': text})
    note('item/completed', {'threadId': tid, 'turnId': turn, 'item': {**entry, 'text': text}})
    turns[turn]['items'].append({**entry, 'text': text})


def finish(tid, turn, status='completed'):
    turns[turn]['status'] = status
    note('turn/completed', {'threadId': tid, 'turn': turns[turn]})


for line in sys.stdin:
    request = json.loads(line)
    log.write(line if line.endswith(LINE) else line + LINE)
    log.flush()
    method, params, rid = request.get('method'), request.get('params') or {}, request.get('id')
    if method is None and rid in waiting:
        tid, turn, kind = waiting.pop(rid)
        result = request.get('result') or {}
        if kind == 'approve':
            message(tid, turn, 'decision: ' + str(result.get('decision')))
        else:
            message(tid, turn, 'answer: ' + json.dumps(result.get('answers'), sort_keys=True))
        finish(tid, turn)
        continue
    if rid is None:
        continue
    reply = {}
    if method in ('thread/turns/list', 'turn/steer') and params.get('threadId') == '00000000-0000-0000-0000-000000000000':
        if old and method == 'turn/steer':
            send({'id': rid, 'error': {'code': -32601, 'message': 'unknown method'}})
        else:
            send({'id': rid, 'error': {'code': -32600, 'message': 'thread not found'}})
        continue
    if method == 'thread/start':
        tid = f't{len(threads) + 1}'
        threads[tid] = {'cwd': params.get('cwd')}
        reply = {'thread': thread(tid)}
        note('thread/started', {'thread': thread(tid)})
    elif method == 'thread/resume':
        reply = {'thread': thread(params['threadId'])}
    elif method == 'thread/list':
        reply = {'data': [thread(t, preview=threads[t].get('preview', '')) for t in threads if not threads[t].get('archived')]}
    elif method == 'thread/turns/list':
        mine = [t for t in turns.values() if t['thread'] == params['threadId']]
        reply = {'data': [{k: v for k, v in t.items() if k != 'thread'} for t in reversed(mine)], 'nextCursor': None}
    elif method == 'thread/name/set':
        threads[params['threadId']]['name'] = params['name']
    elif method == 'thread/archive':
        threads[params['threadId']]['archived'] = True
    elif method == 'turn/start':
        tid = params['threadId']
        text = next((i.get('text', '') for i in params['input'] if i['type'] == 'text'), '')
        threads[tid].setdefault('preview', text)
        turn = f'u{len(turns) + 1}'
        turns[turn] = {'id': turn, 'thread': tid, 'items': [{'type': 'userMessage', 'id': turn + '-user', 'content': params['input']}],
                       'status': 'inProgress', 'error': None}
        send({'id': rid, 'result': {'turn': {'id': turn, 'items': [], 'status': 'inProgress'}}})
        note('turn/started', {'threadId': tid, 'turn': {'id': turn, 'items': [], 'status': 'inProgress'}})
        note('item/started', {'threadId': tid, 'turnId': turn, 'item': turns[turn]['items'][0]})
        note('item/completed', {'threadId': tid, 'turnId': turn, 'item': turns[turn]['items'][0]})
        if 'approve' in text:
            ask = next(asked)
            waiting[ask] = (tid, turn, 'approve')
            send({'id': ask, 'method': 'item/commandExecution/requestApproval',
                  'params': {'threadId': tid, 'turnId': turn, 'itemId': 'c1', 'command': 'touch ../outside', 'reason': 'write outside'}})
        elif 'ask' in text:
            ask = next(asked)
            waiting[ask] = (tid, turn, 'ask')
            send({'id': ask, 'method': 'item/tool/requestUserInput',
                  'params': {'threadId': tid, 'turnId': turn, 'itemId': 'q1', 'isBlocking': True,
                             'questions': [{'id': 'goal', 'header': 'Goal', 'question': 'What for?', 'isOther': True,
                                            'isSecret': False, 'options': [{'label': 'Exam', 'description': ''}]}]}})
        elif 'wait' not in text:
            message(tid, turn, 'done')
            finish(tid, turn)
        continue
    elif method == 'turn/steer':
        turn = params['expectedTurnId']
        text = next((i.get('text', '') for i in params['input'] if i['type'] == 'text'), '')
        message(turns[turn]['thread'], turn, 'steered: ' + text, item='s')
        send({'id': rid, 'result': {'turnId': turn}})
        finish(turns[turn]['thread'], turn)
        continue
    elif method == 'turn/interrupt':
        send({'id': rid, 'result': {}})
        finish(params['threadId'], params['turnId'], 'interrupted')
        continue
    elif method == 'skills/list':
        reply = {'data': [{'cwd': params['cwds'][0], 'errors': [], 'skills': [
            {'name': 'throughline', 'path': '/skills/throughline/SKILL.md', 'description': 'Build or change a course',
             'interface': {'displayName': 'Throughline', 'shortDescription': 'Build a course'}, 'enabled': True, 'scope': 'user'},
            {'name': 'off', 'path': '/skills/off/SKILL.md', 'description': 'Disabled', 'enabled': False, 'scope': 'user'}]}]}
    elif method == 'fuzzyFileSearch':
        reply = {'files': [{'root': params['roots'][0], 'path': 'inputs/waves.md', 'file_name': 'waves.md', 'score': 9},
                           {'root': params['roots'][0], 'path': 'course.sqlite3', 'file_name': 'course.sqlite3', 'score': 1}]}
    elif method == 'windowsSandbox/readiness':
        reply = {'status': 'notConfigured'}
    send({'id': rid, 'result': reply})
