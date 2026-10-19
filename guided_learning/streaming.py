"""Durable model delivery state; partial text never becomes teaching evidence."""
import time
from .store import OperationError
from .teaching import require_text, validate_concept, record_interaction


def read(store, request):
    turn = store.get('streams', require_text(request, 'id'))
    if turn is None:
        raise OperationError('unknown_turn', request['id'])
    return {'turn': turn}


def start(store, request):
    identifier = require_text(request, 'id')
    concept = require_text(request, 'concept_id')
    validate_concept(store, concept)
    prompt = require_text(request, 'prompt')
    identity = {'id':identifier, 'concept_id':concept, 'prompt':prompt, 'channel':request.get('channel','mainline')}
    if identity['channel'] not in ('mainline','sidequestion','practice','preparation'):
        raise OperationError('invalid_channel','Unknown teaching channel')
    old = store.get('streams', identifier)
    if old:
        if any(old[k] != v for k,v in identity.items()):
            raise OperationError('id_conflict', identifier)
        return {'turn':old, 'created':False}
    record_interaction(store, {'id':'stream-user:'+identifier, 'role':'user', 'text':prompt, 'concept_id':concept})
    turn = {**identity, 'attempt':1, 'status':'running', 'text':'', 'final_text':None, 'sequence':0,
            'started_at':time.time(), 'metrics':{}, 'attempts':[], 'resume_requests':[]}
    store.put('streams', identifier, turn)
    return {'turn':turn, 'created':True}


def event(store, request):
    turn = read(store, request)['turn']
    if request.get('attempt') != turn['attempt'] or turn['status'] != 'running':
        return {'turn':turn, 'ignored':True}
    sequence = request.get('sequence')
    if not isinstance(sequence,int) or sequence <= 0:
        raise OperationError('invalid_event', 'Positive sequence required')
    if sequence <= turn['sequence']:
        return {'turn':turn, 'ignored':True}
    if sequence != turn['sequence'] + 1:
        raise OperationError('event_gap', 'Events must be applied in order')
    kind = request.get('kind')
    elapsed = time.time() - turn['started_at']
    if kind == 'delta':
        turn['text'] += request.get('text','')
        turn['metrics'].setdefault('first_delta_s',elapsed)
        if len(turn['text']) >= 200:
            turn['metrics'].setdefault('first_200_chars_s',elapsed)
    elif kind == 'final':
        turn['final_text'] = require_text(request,'text')
    elif kind == 'complete':
        if not turn['final_text']:
            raise OperationError('missing_final','No authoritative final answer')
        begin = time.perf_counter()
        record_interaction(store, {'id':'stream:'+turn['id'], 'role':'assistant', 'text':turn['final_text'], 'concept_id':turn['concept_id']})
        turn['text'] = turn['final_text']
        turn['status'] = 'completed'
        turn['metrics'].update(full_s=elapsed, save_s=time.perf_counter()-begin)
    elif kind == 'failed':
        turn['status'] = 'failed'
        turn['error'] = request.get('error','Model connection ended before completion')
    else:
        raise OperationError('invalid_event', str(kind))
    turn['sequence'] = sequence
    store.put('streams',turn['id'],turn)
    return {'turn':turn}

OPERATIONS = {'stream.start':start, 'stream.read':read, 'stream.event':event,
              'stream.list':lambda s,r:{'turns':sorted(s.list('streams'),key=lambda t:t['started_at'])}}


def pause(store, request):
    turn = read(store,request)['turn']
    if turn['status'] == 'running':
        turn['status'] = 'paused'
        store.put('streams',turn['id'],turn)
    return {'turn':turn}


def resume(store, request):
    turn = read(store,request)['turn']
    request_id = require_text(request,'request_id')
    if request_id in turn['resume_requests']:
        return {'turn':turn,'created':False}
    if turn['status'] not in ('paused','interrupted','failed'):
        raise OperationError('invalid_transition','Only incomplete turns can be regenerated')
    turn['attempts'].append({k:turn.get(k) for k in ('attempt','text','status','metrics','error')})
    turn.update(attempt=turn['attempt']+1,status='running',text='',final_text=None,sequence=0,started_at=time.time(),metrics={})
    turn.pop('error',None)
    turn['resume_requests'].append(request_id)
    store.put('streams',turn['id'],turn)
    return {'turn':turn,'created':True}


def recover(store, request):
    for turn in store.list('streams'):
        if turn['status'] == 'running':
            turn['status'] = 'interrupted'
            turn['error'] = 'Learning server stopped; regenerate to resume this lesson'
            store.put('streams',turn['id'],turn)
    return OPERATIONS['stream.list'](store,request)

OPERATIONS.update({'stream.pause':pause,'stream.resume':resume,'stream.recover':recover})
