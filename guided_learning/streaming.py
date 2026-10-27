"""Durable model delivery state; partial text never becomes teaching evidence."""
import time
from copy import deepcopy
from .store import OperationError
from . import curriculum
from .teaching import resume as session_resume
from .teaching import require_text, validate_concept, record_interaction
from .preferences import view as preferences, validate_language
from .memory import for_prompt as course_memory


# Turn channels, in one place for the host and its features; web/src/lib/types.ts mirrors CHANNELS.
LEARNER_CHANNELS = ('mainline', 'sidequestion', 'practice')  # the learner's own requests
# A lesson step written ahead while the learner reads the current one: hidden, and no teaching interaction, until
# lesson.step reveals it as a mainline turn (ADR 0009).
PREPARED_STEP = 'prepared_step'
BACKGROUND = ('preparation', 'build', 'consolidation')  # channels whose turns are not teaching interactions
SMALL_MODEL = ('preparation', 'consolidation')  # channels the small model serves
CHANNELS = LEARNER_CHANNELS + (PREPARED_STEP,) + BACKGROUND


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
    if identity['channel'] not in CHANNELS:
        raise OperationError('invalid_channel','Unknown teaching channel')
    if 'chapter_id' in request:
        # A turn owned by a chapter (its recap) is shown on the chapter page; concept_id stays the chapter's last
        # section, the anchor for the section-scoped records every turn has (ADR 0006).
        chapter = next((c for c in curriculum.model(store)['chapters'] if c['id'] == request['chapter_id']), None)
        if not chapter or chapter['concept_ids'][-1:] != [concept]:
            raise OperationError('invalid_request','A chapter turn is anchored to the last section of its chapter')
        identity['chapter_id'] = chapter['id']
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
    model = curriculum.model(store)
    concepts = {c['id']:c for c in model['concepts']}
    route = deepcopy([{k:concepts[cid][k] for k in ('id','title','prerequisites') if k in concepts[cid]} for cid in model['route'] if cid in concepts])
    session = session_resume(store,{})
    session.pop('app_questions', None)  # for Codex resuming in chat; the branch prompt already carries the question being answered
    session.pop('context', None)  # the learner's section again, sources and all; context.position already says where they are
    snapshot = {'context':context,'route':route,'session':session,'language':identity['language']}
    if model['chapters']: snapshot['chapters'] = deepcopy([{k:c[k] for k in ('id','title','concept_ids')} for c in model['chapters']])
    profile = store.get('course','profile')
    if profile: snapshot['learner_profile'] = profile
    memory = course_memory(store)  # confirmed preferences, taught terms and current difficulties (ADR 0010)
    if memory and identity['channel'] not in ('build','consolidation'): snapshot['course_memory'] = memory
    if identity['channel'] == PREPARED_STEP:
        # The step it writes and the check repair it assumed, so Continue can tell whether its prompt still applies.
        step = request.get('lesson_step')
        if not isinstance(step, dict):
            raise OperationError('invalid_request','A prepared step names its lesson_step')
        snapshot['lesson_step'] = step
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
                if ref not in source_refs:
                    source_refs.append(ref)
                    # The passage may come from an earlier section, so give the teacher its sources too.
                    context['sources'].append({**ref, **curriculum.source_unit(store,ref), 'stale':curriculum.is_stale(store,ref)})
    turn = {**identity, 'source_refs':source_refs, 'prompt_snapshot':snapshot, 'attempt':1, 'status':'running', 'text':'', 'final_text':None, 'sequence':0,
            'started_at':time.time(), 'metrics':{}, 'attempts':[], 'resume_requests':[]}
    store.put('streams', identifier, turn)
    return {'turn':turn, 'created':True}


def reveal(store, turn):
    """A prepared step becomes the mainline turn the learner asked for with Continue; a completed one is now taught."""
    if turn['channel'] != PREPARED_STEP:
        raise OperationError('invalid_transition', 'Only a prepared step is revealed')
    turn.update(channel='mainline', record_user=True)
    record_interaction(store, {'id':'stream-user:'+turn['id'], 'role':'user', 'text':turn['prompt'], 'concept_id':turn['concept_id']})
    if turn['status'] == 'completed':
        record_interaction(store, {'id':'stream:'+turn['id'], 'role':'assistant', 'text':turn['final_text'], 'concept_id':turn['concept_id'], 'source_refs':turn.get('source_refs',[])})
    store.put('streams', turn['id'], turn)
    return turn


def _apply(store, turn, request):
    """Apply one event to a turn in memory; False when it is stale (another attempt, a stopped turn, or already applied)."""
    if request.get('attempt') != turn['attempt'] or turn['status'] != 'running':
        return False
    sequence = request.get('sequence')
    if not isinstance(sequence,int) or sequence <= 0:
        raise OperationError('invalid_event', 'Positive sequence required')
    if sequence <= turn['sequence']:
        return False
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
        # Background work is not a teaching interaction.
        if turn['channel'] not in BACKGROUND + (PREPARED_STEP,):
            record_interaction(store, {'id':'stream:'+turn['id'], 'role':'assistant', 'text':turn['final_text'], 'concept_id':turn['concept_id'], 'source_refs':turn.get('source_refs',[])})
        turn['text'] = turn['final_text']
        turn['status'] = 'completed'
        turn['metrics'].update(full_s=elapsed, save_s=time.perf_counter()-begin)
        if isinstance(request.get('usage'), dict):
            turn['metrics']['usage'] = request['usage']
    elif kind == 'failed':
        turn['status'] = 'failed'
        turn['error'] = request.get('error','Model connection ended before completion')
    else:
        raise OperationError('invalid_event', str(kind))
    turn['sequence'] = sequence
    return True


def event(store, request):
    turn = read(store, request)['turn']
    if not _apply(store, turn, request):
        return {'turn':turn, 'ignored':True}
    store.put('streams',turn['id'],turn)
    return {'turn':turn}


def events(store, request):
    """Several events of one attempt, in order, written once: the host stores streamed text a few times a second."""
    turn = read(store, request)['turn']
    batch = request.get('events')
    if not isinstance(batch, list) or not all(isinstance(e, dict) for e in batch):
        raise OperationError('invalid_request', 'events must be an array of event objects')
    applied = [_apply(store, turn, {**e, 'attempt': request.get('attempt')}) for e in batch]
    if not any(applied):
        return {'turn':turn, 'ignored':True}
    store.put('streams',turn['id'],turn)
    return {'turn':turn}

OPERATIONS = {'stream.start':start, 'stream.read':read, 'stream.event':event, 'stream.events':events,
              'stream.list':lambda s,r:{'turns':sorted(s.list('streams'),key=lambda t:t['started_at'])}}


def summarize(turn):
    """A turn without its frozen prompt snapshot, which the browser never needs."""
    summary = {k: v for k, v in turn.items() if k not in ('prompt_snapshot', 'resume_requests')}
    summary['attempts'] = [{'attempt': a.get('attempt'), 'text': a.get('text'), 'status': a.get('status')} for a in turn.get('attempts', [])]
    concept = (turn.get('prompt_snapshot') or {}).get('context', {}).get('concept') or {}
    summary['title'] = concept.get('title')
    return summary


BRIEF_DROP = ('prompt_snapshot', 'resume_requests', 'attempts', 'text', 'final_text', 'metrics', 'source_refs', 'prompt')


def brief(turn):
    return {k: v for k, v in turn.items() if k not in BRIEF_DROP}


def summaries(store, request):
    """Turns as the interface shows them, oldest first. `brief` keeps only identity, channel, section and status.
    Only turns changed since the last listing are decoded (`Store.digest`)."""
    turns = store.digest('streams', brief if request.get('brief') is True else summarize)
    return {'turns': sorted(turns, key=lambda t: t['started_at'])}

OPERATIONS['stream.summaries'] = summaries


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
