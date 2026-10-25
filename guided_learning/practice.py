"""Durable exercises and provenance-backed teacher assessments."""
import json
from . import curriculum, evidence, teaching
from .store import OperationError

def listing(store, request):
    return {'tasks':store.list('practice_tasks'),'jobs':store.list('practice_jobs')}

ACTIONS=('generate','hint','steps','solution','assess')

class FormatError(ValueError):
    """The teacher's reply is not the JSON the practice prompt asked for; a model problem, not a course error."""

def job(store, request):
    value = request.get('job')
    if not isinstance(value,dict):
        raise OperationError('invalid_request','job must be an object')
    teaching.require_text(value,'id')
    teaching.require_text(value,'concept_id')
    if value.get('action') not in ACTIONS:
        raise OperationError('invalid_request','action must be one of '+', '.join(ACTIONS))
    if value['action']!='generate':
        teaching.require_text(value,'task_id')
    if value['action']=='assess':
        teaching.require_text(value,'answer')
    teaching.validate_concept(store,value['concept_id'])
    previous=store.get('practice_jobs',value['id'])
    if previous: return {'job':previous}
    if value.get('task_id') and not store.get('practice_tasks',value['task_id']):
        raise OperationError('unknown_exercise','Unknown exercise')
    if value['action']=='assess':
        teaching.record_interaction(store,{'id':'practice-answer:'+value['id'],'role':'user','concept_id':value['concept_id'],'text':value['answer']})
    store.put('practice_jobs',value['id'],value)
    return {'job':value}

def _parse(store, value, text):
    """Check the teacher's reply completely before anything is written; raises FormatError."""
    try:
        raw=text.strip()
        if raw.startswith('```'): raw=raw.split('\n',1)[1].rsplit('```',1)[0]
        result=json.loads(raw)
        if not isinstance(result,dict): raise FormatError('Expected a JSON object')
        if value['action']=='generate':
            questions=result.get('questions')
            if not isinstance(questions,list) or not 1<=len(questions)<=4: raise FormatError('Expected one to four questions')
            context=curriculum.context(store,{'concept_id':value['concept_id']})
            allowed=context['concept'].get('exercises',[])+context['concept'].get('links',[])
            for q in questions:
                if not isinstance(q,dict) or not isinstance(q.get('question'),str) or not q['question'].strip(): raise FormatError('question must be nonempty text')
                if q.get('origin') not in ('source','self_created'): raise FormatError('Missing question origin')
                refs=q.get('source_refs',[])
                if not isinstance(refs,list) or (q['origin']=='source' and not refs): raise FormatError('Missing exercise source')
                for ref in refs:
                    try: curriculum.source_unit(store,ref)
                    except OperationError as exc: raise FormatError(str(exc)) from exc
                    if not any(all(ref.get(k)==a.get(k) for k in ('source_id','revision','unit_id')) for a in allowed): raise FormatError('Unrelated question source')
        else:
            if not isinstance(result.get('feedback'),str) or not result['feedback'].strip(): raise FormatError('feedback must be nonempty text')
            if value['action']=='assess' and result.get('outcome') not in ('passed','needs_work'): raise FormatError('Assessment must explicitly give outcome')
        return result
    except (json.JSONDecodeError,AttributeError,IndexError,TypeError) as exc:
        raise FormatError(str(exc)) from exc

def complete(store, request):
    value=store.get('practice_jobs',teaching.require_text(request,'id'))
    if not value or value.get('processed'): return {}
    turn=store.get('streams',request['id'])
    if not turn or turn['status']!='completed': return {}
    try:
        result=_parse(store,value,turn['final_text'] or '')
    except FormatError as exc:
        value['error']='Teacher output failed format validation; no mastery recorded: '+str(exc)
        value['processed']=True
        store.put('practice_jobs',value['id'],value)
        return {'job':value}
    # Course errors from here on propagate, so the whole operation rolls back and nothing is half-recorded.
    if value['action']=='generate':
        for index,q in enumerate(result['questions']):
            task={'id':value['id']+':'+str(index),'concept_id':value['concept_id'],'question':q['question'],'origin':q['origin'],
                  'source_refs':q.get('source_refs',[]),'status':'pending','history':[]}
            store.put('practice_tasks',task['id'],task)
    else:
        task=store.get('practice_tasks',value['task_id'])
        if task is None: raise OperationError('unknown_exercise','Unknown exercise')
        feedback=result['feedback']
        iid='practice-feedback:'+value['id']
        teaching.record_interaction(store,{'id':iid,'role':'assistant','text':feedback,'concept_id':task['concept_id'],'source_refs':task['source_refs']})
        base={'id':'practice-evidence:'+value['id'],'concept_id':task['concept_id'],'session_id':'practice:'+task['id'],'exercise_id':task['id']}
        if value['action']=='assess':
            item=evidence.assess(store,{**base,'answer_id':'practice-answer:'+value['id'],'assessment_id':iid,'outcome':result['outcome']})['evidence']
            # Corrective feedback may reveal a method/answer; subsequent retries are assisted.
            evidence.record(store,{**base,'id':'practice-feedback-help:'+value['id'],'interaction_id':iid,'kind':'hint','level':'assessment_feedback'})
            task['status']='attempted'
            task['history'].append({'action':'assess','feedback':feedback,'outcome':result['outcome'],'evidence_id':item['id'],'kind':item['kind'],'answer':value['answer']})
        else:
            evidence.record(store,{**base,'interaction_id':iid,'kind':'demonstrated' if value['action']=='solution' else 'hint','level':value['action']})
            task['history'].append({'action':value['action'],'feedback':feedback})
        store.put('practice_tasks',task['id'],task)
    value['processed']=True
    store.put('practice_jobs',value['id'],value)
    return {'job':value}

def defer(store, request):
    task=store.get('practice_tasks',request['id'])
    if not task: raise OperationError('unknown_exercise','Unknown exercise')
    evidence.defer(store,{'id':'practice-defer:'+task['id'],'concept_id':task['concept_id'],'reason':'Learner chose to practice later','section_id':task['concept_id']})
    task['status']='deferred'
    store.put('practice_tasks',task['id'],task)
    return {'task':task}

OPERATIONS={'practice.list':listing,'practice.job':job,'practice.complete':complete,'practice.defer':defer}
