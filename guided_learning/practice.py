"""Durable exercises and provenance-backed teacher assessments."""
import json
from . import curriculum, evidence, teaching
from .store import OperationError

def listing(store, request):
    return {'tasks':store.list('practice_tasks'),'jobs':store.list('practice_jobs')}

def job(store, request):
    value = request['job']
    teaching.validate_concept(store,value['concept_id'])
    previous=store.get('practice_jobs',value['id'])
    if previous: return {'job':previous}
    if value.get('task_id') and not store.get('practice_tasks',value['task_id']):
        raise OperationError('unknown_exercise','Unknown exercise')
    if value['action']=='assess':
        teaching.record_interaction(store,{'id':'practice-answer:'+value['id'],'role':'user','concept_id':value['concept_id'],'text':value['answer']})
    store.put('practice_jobs',value['id'],value)
    return {'job':value}

def complete(store, request):
    value=store.get('practice_jobs',request['id'])
    if not value or value.get('processed'): return {}
    turn=store.get('streams',request['id'])
    if not turn or turn['status']!='completed': return {}
    try:
        raw=turn['final_text'].strip()
        if raw.startswith('```'): raw=raw.split('\n',1)[1].rsplit('```',1)[0]
        result=json.loads(raw)
        if value['action']=='generate':
            questions=result['questions']
            if not isinstance(questions,list) or not 1<=len(questions)<=4: raise ValueError('Expected one to four questions')
            pending=[]
            for index,q in enumerate(questions):
                question=evidence.required(q,'question')
                if q.get('origin') not in ('source','self_created'): raise ValueError('Missing question origin')
                refs=q.get('source_refs',[])
                if not isinstance(refs,list) or (q['origin']=='source' and not refs): raise ValueError('Missing exercise source')
                context=curriculum.context(store,{'concept_id':value['concept_id']})
                allowed=context['concept'].get('exercises',[])+context['concept'].get('links',[])
                for ref in refs:
                    curriculum.source_unit(store,ref)
                    if not any(all(ref.get(k)==a.get(k) for k in ('source_id','revision','unit_id')) for a in allowed): raise ValueError('Unrelated question source')
                pending.append({'id':value['id']+':'+str(index),'concept_id':value['concept_id'],'question':question,'origin':q['origin'],'source_refs':refs,'status':'pending','history':[]})
            for task in pending: store.put('practice_tasks',task['id'],task)
        else:
            task=store.get('practice_tasks',value['task_id'])
            feedback=evidence.required(result,'feedback')
            iid='practice-feedback:'+value['id']
            if value['action']=='assess' and result.get('outcome') not in ('passed','needs_work'): raise ValueError('Assessment must explicitly give outcome')
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
    except (ValueError,KeyError,TypeError) as exc:
        value['error']='教师输出未通过格式校验，未记为掌握：'+str(exc)
        value['processed']=True
    store.put('practice_jobs',value['id'],value)
    return {'job':value}

def defer(store, request):
    task=store.get('practice_tasks',request['id'])
    if not task: raise OperationError('unknown_exercise','Unknown exercise')
    evidence.defer(store,{'id':'practice-defer:'+task['id'],'concept_id':task['concept_id'],'reason':'学习者选择稍后练习','section_id':task['concept_id']})
    task['status']='deferred'
    store.put('practice_tasks',task['id'],task)
    return {'task':task}

OPERATIONS={'practice.list':listing,'practice.job':job,'practice.complete':complete,'practice.defer':defer}
