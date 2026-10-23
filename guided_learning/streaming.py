"""Durable model delivery state; partial text never becomes teaching evidence."""
import time
from .store import OperationError
from . import curriculum
from .teaching import resume as session_resume
from .teaching import require_text, validate_concept, record_interaction
from .preferences import view as preferences, validate_language


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
    if not isinstance(request.get('record_user', True), bool):
        raise OperationError('invalid_request','record_user must be boolean')
    identity = {'record_user':request.get('record_user',True), 'id':identifier, 'concept_id':concept, 'prompt':prompt, 'channel':request.get('channel','mainline')}
    if identity['channel'] not in ('mainline','sidequestion','practice','preparation'):
        raise OperationError('invalid_channel','Unknown teaching channel')
    old = store.get('streams', identifier)
    # Omitted language on a retry means the original request, not today's preference.
    identity['language'] = validate_language(request.get('language', old.get('language','en') if old else preferences(store,{})['preferences']['language']))
    if old:
        if any(old.get(k, True if k=='record_user' else 'en' if k=='language' else None) != v for k,v in identity.items()):
            raise OperationError('id_conflict', identifier)
        return {'turn':old, 'created':False}
    if identity['record_user']: record_interaction(store, {'id':'stream-user:'+identifier, 'role':'user', 'text':prompt, 'concept_id':concept})
    context = curriculum.context(store, {'concept_id':concept})
    source_refs = []
    for field in ('links','exercises','notations'):
        for ref in context['concept'].get(field,[]):
            exact = {k:ref[k] for k in ('source_id','revision','unit_id')}
            if exact not in source_refs: source_refs.append(exact)
    context['sources'] = [{**ref, **curriculum.source_unit(store,ref), 'stale':curriculum.is_stale(store,ref)} for ref in source_refs]
    model = curriculum.view(store,{})
    route = [{k:c[k] for k in ('id','title','prerequisites') if k in c}
             for cid in model['route'] for c in model['concepts'] if c['id']==cid]
    snapshot = {'context':context,'route':route,'session':session_resume(store,{}),'language':identity['language']}
    branch=next((b for b in store.list('web_branches') if identifier in [b['turn_id'],b.get('supplement_turn_id')] + [r['turn_id'] for r in b.get('replies', [])]),None)
    if branch:
        snapshot['branch']=branch
        history_ids = [branch['turn_id'], branch.get('supplement_turn_id')] + [r['turn_id'] for r in branch.get('replies', [])]
        snapshot['branch']['conversation'] = [
            {'question': prior['prompt'], 'answer': prior['final_text']}
            for tid in history_ids if tid and tid != identifier
            for prior in [store.get('streams', tid)] if prior and prior['status'] == 'completed'
        ]
        selected=branch.get('selected_lecture')
        if selected:
            for ref in selected.get('source_refs',[]):
                if ref not in source_refs: source_refs.append(ref)
    turn = {**identity, 'source_refs':source_refs, 'prompt_snapshot':snapshot, 'attempt':1, 'status':'running', 'text':'', 'final_text':None, 'sequence':0,
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
        if turn['channel'] != 'preparation':
            record_interaction(store, {'id':'stream:'+turn['id'], 'role':'assistant', 'text':turn['final_text'], 'concept_id':turn['concept_id'], 'source_refs':turn.get('source_refs',[])})
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
    language = validate_language(request.get('language',preferences(store,{})['preferences']['language']))
    turn['attempts'].append({k:turn.get(k) for k in ('attempt','text','status','metrics','error','source_refs','prompt_snapshot','language')})
    turn.update(attempt=turn['attempt']+1,status='running',text='',final_text=None,sequence=0,started_at=time.time(),metrics={},language=language)
    if turn.get('prompt_snapshot') is not None:
        turn['prompt_snapshot']={**turn['prompt_snapshot'],'language':language}
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
