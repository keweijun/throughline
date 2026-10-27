"""Durable exercises and provenance-backed teacher assessments."""
import json
import time
from collections import Counter
from . import curriculum, evidence, review, teaching
from .store import OperationError

def listing(store, request):
    return {'tasks':store.list('practice_tasks'),'jobs':store.list('practice_jobs')}

ACTIONS=('generate','hint','steps','solution','assess','ask')
# An ask answers the learner's question about an exercise; it is never assessed and records no evidence (ADR 0011).
# A generate job may ask for retrieval questions instead of a section's exercises (ADR 0008): one question for a spaced
# review of the section, or a chapter quiz: two or three new questions spanning the chapter, asked together with a few
# earlier exercises from its sections.
PURPOSES=('review','chapter_quiz')
# Earlier exercises a chapter quiz asks again, at most.
QUIZ_EARLIER=3

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
    if value['action']=='ask':
        teaching.require_text(value,'question')
    if 'purpose' in value and (value['action']!='generate' or value['purpose'] not in PURPOSES):
        raise OperationError('invalid_request','purpose must be review or chapter_quiz, on a generate job')
    teaching.validate_concept(store,value['concept_id'])
    chapter=None
    if value.get('purpose')=='chapter_quiz':
        chapter=quiz_chapter(store,value)
        if not chapter or chapter['concept_ids'][-1]!=value['concept_id']:
            raise OperationError('invalid_request','A chapter quiz is anchored to the last section of its chapter')
    previous=store.get('practice_jobs',value['id'])
    if previous: return {'job':previous}
    if chapter:
        # The earlier exercises are chosen once, when the quiz is requested, so a replay asks the same ones.
        value={**value,'quiz_id':value['id'],'earlier':quiz_earlier(store,chapter)}
    if value.get('task_id') and not store.get('practice_tasks',value['task_id']):
        raise OperationError('unknown_exercise','Unknown exercise')
    if value['action']=='assess':
        teaching.record_interaction(store,{'id':'practice-answer:'+value['id'],'role':'user','concept_id':value['concept_id'],'text':value['answer']})
    if value['action']=='ask':
        teaching.record_interaction(store,{'id':'practice-question:'+value['id'],'role':'user','concept_id':value['concept_id'],'text':value['question']})
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
            sections=None
            if value['purpose']=='chapter_quiz':
                chapter=quiz_chapter(store,value)
                if not chapter: raise FormatError('The chapter of this quiz is no longer in the course')
                sections=chapter['concept_ids']
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
    if value['action']=='generate' and value.get('purpose')=='chapter_quiz':
        quiz_tasks(store,value,result['questions'])
    elif value['action']=='generate':
        for index,q in enumerate(result['questions']):
            task={'id':value['id']+':'+str(index),'concept_id':value['concept_id'],'question':q['question'],'origin':value.get('purpose') or q['origin'],
                  'source_refs':[] if value.get('purpose') else q.get('source_refs',[]),'status':'pending','history':[]}
            store.put('practice_tasks',task['id'],task)
    else:
        task=store.get('practice_tasks',value['task_id'])
        if task is None: raise OperationError('unknown_exercise','Unknown exercise')
        feedback=result['feedback']
        iid='practice-feedback:'+value['id']
        # The job names the section the evidence is for: the task's own or, for a chapter quiz question, the section it tests.
        cid=value['concept_id']
        teaching.record_interaction(store,{'id':iid,'role':'assistant','text':feedback,'concept_id':cid,'source_refs':task['source_refs']})
        base={'id':'practice-evidence:'+value['id'],'concept_id':cid,'session_id':'practice:'+task['id'],'exercise_id':task['id']}
        if value['action']=='ask':
            task['history'].append({'action':'ask','question':value['question'],'feedback':feedback})
        elif value['action']=='assess':
            request={**base,'answer_id':'practice-answer:'+value['id'],'assessment_id':iid,'outcome':result['outcome']}
            retest=task.get('origin')=='review' or (task.get('origin')=='chapter_quiz' and task.get('tests_concept_ids')==[cid])
            prior=retest_target(store,task,cid) if retest else None
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

def quiz_chapter(store, value):
    chapter_id=value.get('chapter_id')
    if not isinstance(chapter_id,str): return None
    return next((c for c in curriculum.view(store,{})['chapters'] if c['id']==chapter_id and c['concept_ids']),None)

def studied_sections(store):
    """Sections with a completed lesson of their own; a chapter recap is not one."""
    return {t['concept_id'] for t in store.list('streams') if t['channel']=='mainline' and t['status']=='completed' and not t.get('chapter_id')}

def quiz_tier(task):
    """Which earlier exercises a chapter quiz asks first: ones solved with help or needing another try, then ones set
    aside, then ones solved independently. An exercise never answered nor set aside is still open, so it is not asked."""
    last=next((h for h in reversed(task.get('history',[])) if h.get('action')=='assess'),None)
    kind=last.get('kind') if last else None
    if kind in ('hinted','needs_work'): return 0
    if task.get('status')=='deferred': return 1
    if kind in ('independent','retest_passed'): return 2
    return None

def quiz_earlier(store, chapter):
    """Up to QUIZ_EARLIER of the chapter's own exercises to ask again, best first by quiz_tier and spread across sections,
    from studied sections not skipped with the chapter; never review or quiz questions. Among equals, ones asked in
    fewer earlier quizzes come first, so retaking the quiz varies it."""
    sections=chapter['concept_ids']
    allowed=(studied_sections(store)-review.skipped(store))&set(sections)
    tasks=store.list('practice_tasks')
    asked=Counter(t['from_task_id'] for t in tasks if t.get('from_task_id'))
    candidates=[t for t in tasks if t.get('origin') in ('source','self_created') and not t.get('chapter_id')
                and t['concept_id'] in allowed and quiz_tier(t) is not None]
    candidates.sort(key=lambda t:(quiz_tier(t),asked[t['id']],sections.index(t['concept_id'])))
    picked=[]
    for spread in (True,False):
        for task in candidates:
            if len(picked)<QUIZ_EARLIER and task not in picked and not (spread and any(p['concept_id']==task['concept_id'] for p in picked)):
                picked.append(task)
    return [t['id'] for t in sorted(picked,key=lambda t:sections.index(t['concept_id']))]

def quiz_tasks(store, value, questions):
    """The quiz: earlier exercises asked again as new tasks (the originals keep their history), then the new questions.
    Every task belongs to the chapter; concept_id is its last section, the anchor section-scoped records need."""
    common={'concept_id':value['concept_id'],'chapter_id':value['chapter_id'],'quiz_id':value.get('quiz_id',value['id']),
            'origin':'chapter_quiz','status':'pending','history':[],'created_at':time.time()}
    items=[]
    for task_id in value.get('earlier',[]):
        original=store.get('practice_tasks',task_id)
        if original:
            items.append({'question':original['question'],'source_refs':original.get('source_refs',[]),'from_task_id':task_id,
                          'tests_concept_ids':[original['concept_id']]})
    items+=[{'question':q['question'],'source_refs':[],'tests_concept_ids':list(dict.fromkeys(q['tests_concept_ids']))} for q in questions]
    for index,item in enumerate(items):
        identifier=value['id']+':'+str(index)
        store.put('practice_tasks',identifier,{'id':identifier,**common,**item})

def retest_target(store, task, cid):
    """The section's latest independent pass from another session, so an unaided review pass is a retest (evidence.assess)."""
    session='practice:'+task['id']
    passes=[e for e in store.list('evidence') if e['concept_id']==cid and e['kind'] in ('independent','retest_passed')
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
