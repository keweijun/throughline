"""Durable exercises and provenance-backed teacher assessments."""
import json
import re
import time
from collections import Counter
from . import curriculum, images as attached, evidence, memory, review, streaming, teaching
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
# A request for different exercises may carry the learner's note on what should change (ADR 0011), at most this long.
MAX_NOTE=1000

# An answer given only in attached images (images.py) is recorded with this text.
IMAGE_ANSWER='(Answer given in the attached images)'

def section_exercise(task):
    return task.get('origin') in ('source','self_created')

def replaceable(task):
    """An exercise the teacher wrote that the learner has not touched: no answer, ask or help, not set aside or skipped.
    Asking for different exercises replaces these; the course's own exercises are never replaced (ADR 0011)."""
    return task.get('origin')=='self_created' and task.get('status')=='pending' and not task.get('history')

def _check_request(store, value):
    """A request for section exercises may replace untouched ones or ask for a variant of one, with an optional note."""
    if not {'note','replaces','variant_of'}&set(value): return
    if value['action']!='generate' or value.get('purpose'):
        raise OperationError('invalid_request','note, replaces and variant_of go with a request for section exercises')
    if 'note' in value and (not isinstance(value['note'],str) or len(value['note'])>MAX_NOTE):
        raise OperationError('invalid_request',f'note must be text of at most {MAX_NOTE} characters')
    if 'replaces' in value and 'variant_of' in value:
        raise OperationError('invalid_request','A request replaces exercises or asks for a variant, not both')
    if 'replaces' in value:
        ids=value['replaces']
        if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids): raise OperationError('invalid_request','replaces must list exercise ids')
        for i in ids:
            task=store.get('practice_tasks',i) if isinstance(i,str) else None
            if not task or task['concept_id']!=value['concept_id'] or not replaceable(task):
                raise OperationError('not_replaceable','Only untouched exercises the teacher wrote for this section can be replaced')
    if 'variant_of' in value:
        task=store.get('practice_tasks',value['variant_of']) if isinstance(value['variant_of'],str) else None
        if not task or task['concept_id']!=value['concept_id'] or not section_exercise(task):
            raise OperationError('unknown_exercise','A variant is written from one of this section\'s exercises')

class FormatError(ValueError):
    """The teacher's reply is not the JSON the practice prompt asked for; a model problem, not a course error."""

def part_count(task):
    """A task without a parts list, such as one from before parts, is a single part."""
    return len(task.get('parts') or [None])

def part_statuses(task):
    """Each part's status after the latest assessment (ADR 0011): an answer changes only the parts it addresses, so the
    rest stay not_attempted or keep an earlier status. An old assessment without parts gave its one part's status."""
    count=part_count(task)
    last=next((h for h in reversed(task.get('history',[])) if h.get('action')=='assess'),None)
    if last and len(last.get('parts') or [])==count: return list(last['parts'])
    if last and count==1: return ['correct' if last.get('outcome')=='passed' else 'not_yet']
    return ['not_attempted']*count

MAX_PART_LABEL = 40

def _part(p):
    """A part is the text of what it asks, or {label?, text} with a short label such as "(a)"."""
    if isinstance(p,str): return bool(p.strip())
    return (isinstance(p,dict) and not set(p)-{'label','text'} and isinstance(p.get('text'),str) and bool(p['text'].strip())
            and ('label' not in p or isinstance(p['label'],str) and 0<len(p['label'].strip())<=MAX_PART_LABEL))

# Subquestion markers in an exercise written before exercises carried parts: （1） or （a） anywhere; (1) or (a) at a line
# start or after whitespace or punctuation, so that f(1) is not one; or "1." at a line start.
PART_MARK=re.compile(r'（(\d{1,2}|[a-h])）|(?:(?<=[\s。；;，,：:])|^)\((\d{1,2}|[a-h])\)|^[ \t]*(\d{1,2})[.、][ \t]',re.M)

def infer_parts(question):
    """The parts of a question that numbers its subquestions (1, 2, 3, ... or a, b, c, ...), else None."""
    marks=list(PART_MARK.finditer(question))
    keys=[m.group(1) or m.group(2) or m.group(3) for m in marks]
    expected=[str(i+1) for i in range(len(keys))] if keys and keys[0]=='1' else [chr(97+i) for i in range(len(keys))]
    if len(keys)<2 or keys!=expected: return None
    parts=[]
    for i,m in enumerate(marks):
        text=question[m.end():marks[i+1].start() if i+1<len(marks) else len(question)].strip()
        if not text: return None
        parts.append({'label':m.group(0).strip(),'text':text[:200]})
    return parts

def _check_parts(q):
    if 'parts' in q and (not isinstance(q['parts'],list) or not q['parts'] or not all(_part(p) for p in q['parts'])):
        raise FormatError(f'parts must list each part as nonempty text or {{label, text}} with a label of at most {MAX_PART_LABEL} characters')

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
    if 'images' in value and value['action'] not in ('assess','ask'):
        raise OperationError('invalid_request','images go with an answer or a question')
    attached.validate(store.workspace,value)
    if value['action']=='assess':
        # With images attached, the written part of the answer may be empty.
        if not (value.get('images') and isinstance(value.get('answer'),str)): teaching.require_text(value,'answer')
    if value['action']=='ask':
        teaching.require_text(value,'question')
    if 'purpose' in value and (value['action']!='generate' or value['purpose'] not in PURPOSES):
        raise OperationError('invalid_request','purpose must be review or chapter_quiz, on a generate job')
    teaching.validate_concept(store,value['concept_id'])
    _check_request(store,value)
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
        task=store.get('practice_tasks',value['task_id'])
        # An exercise from before parts is assessed by the subquestions its text numbers, from its next answer on.
        if 'parts' not in task and (inferred:=infer_parts(task['question'])):
            store.put('practice_tasks',task['id'],{**task,'parts':inferred})
        answer=teaching.record_interaction(store,{'id':'practice-answer:'+value['id'],'role':'user','concept_id':value['concept_id'],
                                                  'text':value['answer'] if value['answer'].strip() else IMAGE_ANSWER})['interaction']
        if value.get('images'): store.put('interactions',answer['id'],{**answer,'images':value['images']})
    if value.get('note'):
        # The note is the learner's words, which a memory note may cite when it suggests a preference (ADR 0010).
        teaching.record_interaction(store,{'id':'practice-request:'+value['id'],'role':'user','concept_id':value['concept_id'],'text':value['note']})
    if value['action']=='ask':
        question=teaching.record_interaction(store,{'id':'practice-question:'+value['id'],'role':'user','concept_id':value['concept_id'],'text':value['question']})['interaction']
        if value.get('images'): store.put('interactions',question['id'],{**question,'images':value['images']})
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
                sections=quiz_sections(store,chapter)
            for q in questions:
                if not isinstance(q,dict) or not isinstance(q.get('question'),str) or not q['question'].strip(): raise FormatError('question must be nonempty text')
                _check_parts(q)
                if sections is not None:
                    tested=q.get('tests_concept_ids')
                    if not isinstance(tested,list) or not tested or any(c not in sections for c in tested): raise FormatError('tests_concept_ids must list studied sections of this chapter')
        elif value['action']=='generate':
            questions=result.get('questions')
            if not isinstance(questions,list) or not 1<=len(questions)<=4: raise FormatError('Expected one to four questions')
            if value.get('variant_of') and (len(questions)!=1 or questions[0].get('origin')!='self_created'):
                raise FormatError('A variant is exactly one question with origin self_created')
            context=curriculum.context(store,{'concept_id':value['concept_id']})
            allowed=context['concept'].get('exercises',[])+context['concept'].get('links',[])
            for q in questions:
                if not isinstance(q,dict) or not isinstance(q.get('question'),str) or not q['question'].strip(): raise FormatError('question must be nonempty text')
                _check_parts(q)
                if q.get('origin') not in ('source','self_created'): raise FormatError('Missing question origin')
                refs=q.get('source_refs',[])
                if not isinstance(refs,list) or (q['origin']=='source' and not refs): raise FormatError('Missing exercise source')
                for ref in refs:
                    try: curriculum.source_unit(store,ref)
                    except OperationError as exc: raise FormatError(str(exc)) from exc
                    if not any(_same_unit(ref,a) for a in allowed): raise FormatError('Unrelated question source')
                exercises=context['concept'].get('exercises',[])
                if 'exercise' in q:
                    if q['origin']!='source' or not any(e.get('question')==q['exercise'] for e in exercises): raise FormatError('exercise must name one of the section\'s exercises')
                else:
                    # A task from the only exercise of its source unit uses that exercise.
                    used=[e for e in exercises if any(_same_unit(ref,e) for ref in refs)]
                    if q['origin']=='source' and len(used)==1 and isinstance(used[0].get('question'),str): q['exercise']=used[0]['question']
        else:
            if not isinstance(result.get('feedback'),str) or not result['feedback'].strip(): raise FormatError('feedback must be nonempty text')
            if value['action']=='assess':
                task=store.get('practice_tasks',value['task_id'])
                count=part_count(task) if task else 1
                parts=result.get('parts')
                # A reply giving only an outcome still assesses a single-part exercise.
                if parts is None and count==1 and result.get('outcome') in ('passed','needs_work'):
                    parts=['correct' if result['outcome']=='passed' else 'not_yet']
                if not isinstance(parts,list) or len(parts)!=count or any(p not in evidence.PART_STATUSES for p in parts):
                    raise FormatError(f'Assessment must give the status of each of the {count} parts')
                result['parts']=parts
        return result
    except (json.JSONDecodeError,AttributeError,IndexError,TypeError) as exc:
        raise FormatError(str(exc)) from exc

def _same_unit(ref, other):
    return all(ref.get(k)==other.get(k) for k in ('source_id','revision','unit_id'))

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
                  'source_refs':[] if value.get('purpose') else q.get('source_refs',[]),'status':'pending','history':[],'created_at':time.time()}
            if 'parts' in q: task['parts']=q['parts']
            if not value.get('purpose') and 'exercise' in q: task['exercise']=q['exercise']
            if value.get('variant_of'): task['variant_of']=value['variant_of']
            store.put('practice_tasks',task['id'],task)
        # Replaced only once the new exercises exist, and only those the learner still has not touched (ADR 0011).
        for task_id in value.get('replaces',[]):
            task=store.get('practice_tasks',task_id)
            if task and replaceable(task):
                store.put('practice_tasks',task_id,{**task,'status':'replaced','replaced_by':value['id'],'replaced_at':time.time()})
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
            task['history'].append({'action':'ask','question':value['question'],'feedback':feedback,**({'images':value['images']} if value.get('images') else {})})
        elif value['action']=='assess':
            parts=[old if new=='not_attempted' else new for old,new in zip(part_statuses(task),result['parts'])]
            outcome='passed' if all(p=='correct' for p in parts) else 'needs_work'
            request={**base,'answer_id':'practice-answer:'+value['id'],'assessment_id':iid,'outcome':outcome,'parts':parts}
            retest=task.get('origin')=='review' or (task.get('origin')=='chapter_quiz' and task.get('tests_concept_ids')==[cid])
            prior=retest_target(store,task,cid) if retest else None
            if prior: request['retest_of']=prior
            item=evidence.assess(store,request)['evidence']
            # Feedback correcting a part may reveal a method/answer, so later answers are assisted; confirming a correct part is no help.
            if any(p in ('partly_correct','not_yet') for p in result['parts']):
                evidence.record(store,{**base,'id':'practice-feedback-help:'+value['id'],'interaction_id':iid,'kind':'hint','level':'assessment_feedback'})
            task['status']='attempted'
            task['history'].append({'action':'assess','feedback':feedback,'outcome':outcome,'parts':parts,'evidence_id':item['id'],'kind':item['kind'],'answer':value['answer'],
                                    **({'images':value['images']} if value.get('images') else {})})
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

def quiz_sections(store, chapter):
    """The chapter's sections a quiz may test: studied ones not skipped with the chapter."""
    allowed=studied_sections(store)-review.skipped(store)
    return [c for c in chapter['concept_ids'] if c in allowed]

def studied_sections(store):
    """Sections with a completed lesson of their own (a chapter recap is not one) or any learning evidence, such as
    sections taught in Codex chat before the app."""
    return ({t['concept_id'] for t in store.digest('streams',streaming.brief) if t['channel']=='mainline' and t['status']=='completed' and not t.get('chapter_id')}
            | {e['concept_id'] for e in store.list('evidence')})

def quiz_tier(task):
    """Which earlier exercises a chapter quiz asks first: ones solved with help or needing another try, then ones set
    aside, then ones solved independently. An exercise never answered nor set aside is still open, so it is not asked;
    a skipped one is closed for good (ADR 0011)."""
    if task.get('status')=='skipped': return None
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
    allowed=set(quiz_sections(store,chapter))
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
                          'tests_concept_ids':[original['concept_id']],**({'parts':original['parts']} if 'parts' in original else {})})
    items+=[{'question':q['question'],'source_refs':[],'tests_concept_ids':list(dict.fromkeys(q['tests_concept_ids'])),
             **({'parts':q['parts']} if 'parts' in q else {})} for q in questions]
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

SKIP_REASONS=tuple(memory.SKIP_PREFERENCES['en'])  # each reason has the preference it suggests (ADR 0011)

def require_skippable(task):
    if task.get('origin') not in ('source','self_created'):
        raise OperationError('invalid_action','Only a section exercise can be skipped; a review question waits with Not now and a quiz question can stay unanswered')

def skip(store, request):
    """Close a section exercise for good, with an optional reason (ADR 0011). It records no outcome, evidence or deferral;
    answering it later reopens it like any attempt."""
    task=store.get('practice_tasks',request.get('id'))
    if not task: raise OperationError('unknown_exercise','Unknown exercise')
    require_skippable(task)
    reason=request.get('reason')
    if reason is not None and reason not in SKIP_REASONS:
        raise OperationError('invalid_request','reason must be one of '+', '.join(SKIP_REASONS))
    task['status']='skipped'
    task.pop('skip_reason',None)
    if reason: task['skip_reason']=reason
    task['skipped_at']=time.time()
    store.put('practice_tasks',task['id'],task)
    suggested=memory.suggest_from_skips(store,reason,task['concept_id']) if reason else None
    return {'task':task,**({'suggested':suggested} if suggested else {})}

def sections_for_quiz(store, request):
    chapter=quiz_chapter(store,{'chapter_id':request.get('chapter_id')})
    if not chapter: raise OperationError('unknown_chapter','Unknown chapter')
    return {'sections':quiz_sections(store,chapter)}

OPERATIONS={'practice.list':listing,'practice.quiz_sections':sections_for_quiz,'practice.job':job,'practice.complete':complete,'practice.defer':defer,'practice.skip':skip}
