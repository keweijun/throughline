"""Durable side lanes: teacher decisions never mutate the course checkpoint."""
import time
from .store import OperationError
from .migrations import lecture_excerpt
from .teaching import require_text, create_deferred
from .streaming import brief


def read(store, request):
    branch=store.get('web_branches',require_text(request,'id'))
    if branch is None: raise OperationError('unknown_branch',request['id'])
    return {'branch':branch}


def begin(store, request):
    identifier=require_text(request,'id')
    question=require_text(request,'question')
    previous=store.get('web_branches',identifier)
    if previous:
        if previous['question'] != question or previous['selection'] != request.get('selection','') or previous.get('selected_turn_id') != request.get('selected_turn_id'):
            raise OperationError('id_conflict',identifier)
        return {'branch':previous}
    position=store.get('course','position')
    if not position: raise OperationError('missing_mainline','Start a lesson before asking a side question')
    selected_id=request.get('selected_turn_id')
    selected=store.get('streams',selected_id) if selected_id else None
    if selected_id and (not selected or selected['channel']!='mainline'):
        raise OperationError('invalid_selection','Selected passage must belong to a lecture')
    # The current lecture is the section's own lesson; a chapter recap anchored there is not the mainline.
    mains=sorted((t for t in store.digest('streams',brief) if t['channel']=='mainline' and t['concept_id']==position.get('concept_id') and not t.get('chapter_id')),key=lambda t:t['started_at'])
    current_id=mains[-1]['id'] if mains else None
    if request.get('main_turn_id') and request['main_turn_id']!=current_id:
        raise OperationError('stale_mainline','Refresh the current lecture before asking')
    anchor=request.get('anchor',{})
    if not isinstance(anchor,dict): raise OperationError('invalid_request','anchor must be an object')
    branch={'id':identifier,'question':question,'selection':request.get('selection',''), 'anchor':anchor,
            'restore_point':position,'main_turn_id':current_id,
            'selected_turn_id':selected_id,'selected_lecture':lecture_excerpt(selected) if selected else None, 'turn_id':'branch:'+identifier,
            'status':'unanswered','decision':None,'choice':None,'created_at':time.time(),'replies':[]}
    store.put('web_branches',identifier,branch)
    return {'branch':branch}

OPERATIONS={'branch.begin':begin,'branch.read':read}


def decide(store,request):
    branch=read(store,request)['branch']
    if branch['status']!='unanswered': return {'branch':branch}
    turn=store.get('streams',branch['turn_id'])
    if not turn or turn['status']!='completed': raise OperationError('incomplete_answer','Complete reply required')
    decision=request.get('decision',{})
    if not isinstance(decision,dict): raise OperationError('invalid_decision','Teacher decision must be an object')
    if (decision.get('depth') not in ('short','long') or decision.get('category') not in ('local','prerequisite','future','repeated','extension')
            or not isinstance(decision.get('rationale'),str) or not decision['rationale'].strip()
            or not isinstance(decision.get('suggest_supplement'),bool)):
        raise OperationError('invalid_decision','Teacher decision is incomplete')
    if decision['suggest_supplement'] and not str(decision.get('supplement_goal','')).strip():
        raise OperationError('invalid_decision','Supplement goal required')
    if decision['category']=='future' and decision['depth']=='short':
        try:
            create_deferred(store,{'id':'web:'+branch['id'],'interaction_id':'stream-user:'+branch['turn_id'],
                'provisional_answer_interaction_id':'stream:'+branch['turn_id'],'target_concept_id':decision.get('target_concept_id')})
        except OperationError as exc:
            # An unknown target section loses only the schedule, never the answer's route note.
            if exc.code not in ('invalid_request','unknown_concept'): raise
            decision={**decision,'target_concept_id':None}
    branch.update(decision=decision,status='suggested' if decision['suggest_supplement'] else 'answered')
    store.put('web_branches',branch['id'],branch)
    return {'branch':branch}


def choose(store,request):
    branch=read(store,request)['branch']
    choice=request.get('choice')
    if choice not in ('accept','decline'): raise OperationError('invalid_choice','accept or decline required')
    if branch['choice']:
        if branch['choice']!=choice: raise OperationError('invalid_transition','Suggestion already decided')
        return {'branch':branch}
    if branch['status']!='suggested': raise OperationError('invalid_transition','No supplement suggestion')
    if choice=='accept':
        if store.get('course','position')!=branch['restore_point']:
            raise OperationError('stale_branch','Mainline changed; ask again in current context')
        main=store.get('streams',branch.get('main_turn_id')) if branch.get('main_turn_id') else None
        if main and main['status']=='running': raise OperationError('main_running','Pause mainline before accepting')
        branch['supplement_turn_id']='supplement:'+branch['id']
    branch.update(choice=choice,status='supplement' if choice=='accept' else 'answered')
    store.put('web_branches',branch['id'],branch)
    return {'branch':branch}


def return_mainline(store,request):
    branch=read(store,request)['branch']
    # Never restore an old position over newer navigation. Returning controls reading, not progress.
    branch['returned']=True
    store.put('web_branches',branch['id'],branch)
    return {'branch':branch,'position':store.get('course','position')}

OPERATIONS.update({'branch.decide':decide,'branch.choose':choose,'branch.return':return_mainline})


def listing(store, request):
    branches = store.list('web_branches')
    for branch in branches:
        turn = store.get('streams', branch['turn_id']) or {}
        branch.setdefault('created_at', turn.get('started_at', 0))
    return {'branches': sorted(branches, key=lambda b: (b['created_at'], b['id']))}


def reply(store, request):
    branch = read(store, request)['branch']
    identifier = require_text(request, 'reply_id')
    question = require_text(request, 'question')
    selection = request.get('selection', '')
    if not isinstance(selection, str):
        raise OperationError('invalid_request', 'selection must be text')
    replies = branch.setdefault('replies', [])
    previous = next((r for r in replies if r['id'] == identifier), None)
    if previous:
        if previous['question'] != question or previous['selection'] != selection:
            raise OperationError('id_conflict', identifier)
        return {'branch': branch, 'reply': previous}
    turns = [branch['turn_id'], branch.get('supplement_turn_id')] + [r['turn_id'] for r in replies]
    for turn_id in filter(None, turns):
        turn = store.get('streams', turn_id)
        if not turn or turn['status'] != 'completed':
            raise OperationError('incomplete_answer', 'Finish or regenerate the earlier reply before following up')
    item = {'id': identifier, 'question': question, 'selection': selection,
            'turn_id': 'reply:' + branch['id'] + ':' + identifier, 'created_at': time.time()}
    replies.append(item)
    store.put('web_branches', branch['id'], branch)
    return {'branch': branch, 'reply': item}


OPERATIONS.update({'branch.list': listing, 'branch.reply': reply})
