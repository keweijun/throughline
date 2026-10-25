"""Durable exercises and provenance-backed teacher assessments."""
import json
from . import curriculum, evidence, teaching
from .store import OperationError

def listing(store, request):
    return {'tasks':store.list('practice_tasks'),'jobs':store.list('practice_jobs')}

ACTIONS=('generate','hint','steps','solution','assess')
# A generate job may ask for retrieval questions instead of a section's exercises (ADR 0008): one question for a spaced
# review of the section, or two or three spanning a chapter after its recap, in the chapter's last section.
PURPOSES=('review','recap')

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
    if 'purpose' in value and (value['action']!='generate' or value['purpose'] not in PURPOSES):
        raise OperationError('invalid_request','purpose must be review or recap, on a generate job')
    teaching.validate_concept(store,value['concept_id'])
    if value.get('purpose')=='recap':
        chapter=curriculum.context(store,{'concept_id':value['concept_id']})['chapter']
        if not chapter or chapter['concept_ids'][-1]!=value['concept_id']:
            raise OperationError('invalid_request','Recap questions belong to the last section of a chapter')
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
        if value['action']=='generate' and value.get('purpose'):
            questions=result.get('questions')
            low,high=(1,1) if value['purpose']=='review' else (2,3)
            if not isinstance(questions,list) or not low<=len(questions)<=high: raise FormatError(f'Expected {low} to {high} questions' if low!=high else 'Expected exactly one question')
            sections=recap_sections(store,value) if value['purpose']=='recap' else None
            for q in questions:
                if not isinstance(q,dict) or not isinstance(q.get('question'),str) or not q['question'].strip(): raise FormatError('question must be nonempty text')
                if sections is not None:
                    tested=q.get('tests_concept_ids')
                    if not isinstance(tested,list) or not tested or any(c not in sections for c in tested): raise FormatError('tests_concept_ids must list sections of this chapter')
        elif value['action']=='generate':
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
            task={'id':value['id']+':'+str(index),'concept_id':value['concept_id'],'question':q['question'],'origin':value.get('purpose') or q['origin'],
                  'source_refs':[] if value.get('purpose') else q.get('source_refs',[]),'status':'pending','history':[]}
            if value.get('purpose')=='recap':
                task['tests_concept_ids']=list(dict.fromkeys(q['tests_concept_ids']))
            store.put('practice_tasks',task['id'],task)
    else:
        task=store.get('practice_tasks',value['task_id'])
        if task is None: raise OperationError('unknown_exercise','Unknown exercise')
        feedback=result['feedback']
        iid='practice-feedback:'+value['id']
        teaching.record_interaction(store,{'id':iid,'role':'assistant','text':feedback,'concept_id':task['concept_id'],'source_refs':task['source_refs']})
        base={'id':'practice-evidence:'+value['id'],'concept_id':task['concept_id'],'session_id':'practice:'+task['id'],'exercise_id':task['id']}
        if value['action']=='assess':
            request={**base,'answer_id':'practice-answer:'+value['id'],'assessment_id':iid,'outcome':result['outcome']}
            prior=retest_target(store,task) if task.get('origin')=='review' else None
            if prior: request['retest_of']=prior
            item=evidence.assess(store,request)['evidence']
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

def recap_sections(store, value):
    return curriculum.context(store,{'concept_id':value['concept_id']})['chapter']['concept_ids']

def retest_target(store, task):
    """The section's latest independent pass from another session, so an unaided review pass is a retest (evidence.assess)."""
    session='practice:'+task['id']
    passes=[e for e in store.list('evidence') if e['concept_id']==task['concept_id'] and e['kind'] in ('independent','retest_passed')
            and e.get('session_id')!=session and store.get('interactions',e['assessment_id'])]
    latest=max(passes,key=lambda e:store.get('interactions',e['assessment_id'])['sequence'],default=None)
    return latest['id'] if latest else None

def defer(store, request):
    task=store.get('practice_tasks',request['id'])
    if not task: raise OperationError('unknown_exercise','Unknown exercise')
    evidence.defer(store,{'id':'practice-defer:'+task['id'],'concept_id':task['concept_id'],'reason':'Learner chose to practice later','section_id':task['concept_id']})
    task['status']='deferred'
    store.put('practice_tasks',task['id'],task)
    return {'task':task}

OPERATIONS={'practice.list':listing,'practice.job':job,'practice.complete':complete,'practice.defer':defer}
