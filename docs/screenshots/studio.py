"""A stand-in `codex app-server` for the README screenshots: python studio.py <log>.

Studio talks to it as to Codex. A message that contains a key of studio-scripts.json gets that script's reply: reasoning,
commentary and commands, then the answer, as Codex would show them; anything else gets "Done.". Chats last as long as
the process. Like tests/fake_studio_server.py, which covers the protocol in full, but only what the screenshots need."""
import json
import sys
import time
from pathlib import Path

SCRIPTS = json.loads(Path(__file__).with_name('studio-scripts.json').read_text(encoding='utf-8'))
log = open(sys.argv[1], 'a', encoding='utf-8')
threads, turns = {}, {}


def send(message):
    sys.stdout.write(json.dumps(message) + '\n')
    sys.stdout.flush()


def note(method, params):
    send({'method': method, 'params': params})


def thread(tid):
    return {'id': tid, 'name': None, 'preview': '', 'createdAt': 1, 'updatedAt': int(time.time()), 'status': {'type': 'idle'},
            'turns': [], **threads[tid]}


def item(tid, turn, entry, delta=None):
    note('item/started', {'threadId': tid, 'turnId': turn, 'item': {**entry, 'text': ''} if delta else entry})
    if delta:
        note('item/agentMessage/delta', {'threadId': tid, 'turnId': turn, 'itemId': entry['id'], 'delta': delta})
    note('item/completed', {'threadId': tid, 'turnId': turn, 'item': entry})
    turns[turn]['items'].append(entry)


def say(tid, turn, text, key, phase='final_answer'):
    item(tid, turn, {'type': 'agentMessage', 'id': f'{turn}-{key}', 'text': text, 'phase': phase}, delta=text)


def play(tid, turn, text):
    script = next((s for key, s in SCRIPTS.items() if key in text), None)
    if script is None:
        say(tid, turn, 'Done.', 'm')
        return
    for n, step in enumerate(script['items']):
        if step['type'] == 'say':
            say(tid, turn, step['text'], f'c{n}', 'commentary')
        elif step['type'] == 'think':
            item(tid, turn, {'type': 'reasoning', 'id': f'{turn}-r{n}', 'summary': [step['text']], 'content': []})
        else:
            item(tid, turn, {'type': 'commandExecution', 'id': f'{turn}-x{n}', 'command': step['command'], 'cwd': '.',
                             'status': 'completed', 'commandActions': [{'type': 'unknown', 'command': step['command']}],
                             'aggregatedOutput': step.get('output', ''), 'exitCode': 0})
    say(tid, turn, script['answer'], 'm')
    turns[turn]['startedAt'] -= 94  # a real turn of this size takes a minute or two


for line in sys.stdin:
    log.write(line)
    log.flush()
    request = json.loads(line)
    method, params, rid = request.get('method'), request.get('params') or {}, request.get('id')
    if rid is None or method is None:
        continue
    reply = {}
    if params.get('threadId') == '00000000-0000-0000-0000-000000000000':
        # Studio checks at start-up that these methods exist: they do, and the thread does not.
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
        reply = {'data': [thread(t) for t in threads]}
    elif method == 'thread/turns/list':
        mine = [t for t in turns.values() if t['thread'] == params['threadId']]
        reply = {'data': [{k: v for k, v in t.items() if k != 'thread'} for t in reversed(mine)], 'nextCursor': None}
    elif method == 'thread/name/set':
        threads[params['threadId']]['name'] = params['name']
    elif method == 'turn/start':
        tid = params['threadId']
        text = next((i.get('text', '') for i in params['input'] if i['type'] == 'text'), '')
        threads[tid].setdefault('preview', text)
        turn = f'u{len(turns) + 1}'
        turns[turn] = {'id': turn, 'thread': tid, 'items': [], 'status': 'inProgress', 'error': None, 'startedAt': time.time()}
        send({'id': rid, 'result': {'turn': {'id': turn, 'items': [], 'status': 'inProgress'}}})
        note('turn/started', {'threadId': tid, 'turn': {'id': turn, 'items': [], 'status': 'inProgress'}})
        item(tid, turn, {'type': 'userMessage', 'id': turn + '-user', 'content': params['input']})
        if params.get('outputSchema'):
            # The chat's title, which Studio asks for beside the first message.
            title = next((s['title'] for key, s in SCRIPTS.items() if key in text), 'Course work')
            say(tid, turn, json.dumps({'title': title}), 'm')
        else:
            play(tid, turn, text)
        turns[turn].update(status='completed', completedAt=time.time())
        turns[turn]['durationMs'] = int((turns[turn]['completedAt'] - turns[turn]['startedAt']) * 1000)
        note('turn/completed', {'threadId': tid, 'turn': turns[turn]})
        continue
    elif method == 'turn/interrupt':
        pass
    elif method == 'skills/list':
        reply = {'data': [{'cwd': params['cwds'][0], 'errors': [], 'skills': [
            {'name': 'throughline', 'path': '/skills/throughline/SKILL.md', 'description': 'Build or change a course',
             'interface': {'displayName': 'Throughline', 'shortDescription': 'Build a course'}, 'enabled': True, 'scope': 'user'}]}]}
    elif method == 'fuzzyFileSearch':
        reply = {'files': []}
    elif method == 'windowsSandbox/readiness':
        reply = {'status': 'ready'}
    send({'id': rid, 'result': reply})
