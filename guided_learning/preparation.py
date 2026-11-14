"""Version-bound preparation material; never learning or interaction evidence."""
import hashlib
import json
import time
from . import curriculum, streaming
from .teaching import require_text
from .store import OperationError
from .preferences import view as preferences


def capture(store, cid):
    context = curriculum.context(store, {'concept_id': cid})
    context.pop('position', None)
    language = preferences(store,{})['preferences']['language']
    # Only what this section's preparation depends on: its own context (section, chapter, prerequisites and the exact
    # source revisions it teaches from), the learner profile and the teaching language. Edits elsewhere in the course,
    # such as another chapter being built, leave it valid.
    data = {'context': context, 'profile': store.get('course', 'profile'), 'language': language}
    return {'fingerprint': hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest(), 'context':context, 'language':language}


def target(store):
    """The section to prepare: the next one on the route, once the learner has started a lesson in the current one.
    Learners who drill exercises without lessons, or jump from section to section, would otherwise leave most of what is
    prepared unread (issue #176); a lesson takes minutes, preparation about a minute, so waiting for it costs no head start."""
    current = store.get('course','position',{}).get('concept_id')
    if not current: return None
    if not any(t['channel'] == 'mainline' and t['concept_id'] == current and not t.get('chapter_id') for t in store.digest('streams', streaming.brief)):
        return None
    return curriculum.context(store,{'concept_id':current})['next_concept_id']


# A job's snapshot and prepared material are kept apart from the job, which keeps the snapshot's fingerprint and
# language: background scheduling reads every job every few seconds, and only prompts read the rest.
PAYLOADS = 'preparation_payloads'
PAYLOAD = ('snapshot', 'content')


def save(store, job):
    """Store a job. A job read with its payload (`load`) stores that too; one read without leaves it as it is."""
    slim = {k: v for k, v in job.items() if k not in PAYLOAD}
    if 'snapshot' in job:
        slim.update(fingerprint=job['snapshot']['fingerprint'], language=job['snapshot'].get('language', 'en'))
    if any(k in job for k in PAYLOAD):
        store.put(PAYLOADS, job['id'], {'id': job['id'], **{k: job[k] for k in PAYLOAD if k in job}})
    store.put('preparation_jobs', job['id'], slim)


def _with_payload(job, payload):
    if payload:
        job.update({k: payload[k] for k in PAYLOAD if k in payload})
    return job


def load(store, identifier):
    """A job with its snapshot and material, or None."""
    job = store.get('preparation_jobs', identifier)
    return job and _with_payload(job, store.get(PAYLOADS, identifier))


def every(store):
    payloads = {p['id']: p for p in store.list(PAYLOADS)}
    return [_with_payload(job, payloads.get(job['id'])) for job in store.list('preparation_jobs')]


def brief(job):
    """A job without its snapshot and material; it keeps the snapshot's teaching language."""
    return {k: v for k, v in job.items() if k not in PAYLOAD + ('fingerprint',)}


def reconcile(store, request):
    current = store.get('course','position',{}).get('concept_id')
    upcoming = target(store)
    for listed in store.digest('preparation_jobs', brief):
        if listed['status'] not in ('running','ready'): continue
        job = store.get('preparation_jobs', listed['id'])
        change = None
        if job['concept_id'] not in (current,upcoming):
            change = {'status':'stale','reason':'The learner moved to another section','content':None}
        elif capture(store,job['concept_id'])['fingerprint'] != job.get('fingerprint'):
            change = {'status':'stale','reason':'Route, sources, or teaching language changed; the main teacher will prepare independently','content':None}
        elif job['status']=='running':
            turn=store.get('streams',job['id'])
            if turn and turn['status']=='completed': change = {'status':'ready','content':turn['final_text']}
            elif turn and turn['status'] in ('failed','interrupted','paused'):
                change = {'status':'deferred' if turn['status']=='paused' else 'failed','reason':turn.get('error','Foreground learning takes priority')}
        # Unchanged jobs are not rewritten, so idle polling writes nothing to the course.
        if change:
            job = {**load(store, job['id']), **change}
            if job.get('content') is None:
                job.pop('content', None)
            save(store, job)
    # `brief` lists jobs without their snapshot and material, decoding only jobs changed since the last listing.
    jobs = store.digest('preparation_jobs', brief) if request.get('brief') is True else every(store)
    return {'jobs':sorted(jobs,key=lambda j:j.get('created_at',0))}


def enqueue(store, request):
    identifier=require_text(request,'id')
    old=load(store,identifier)
    if old: return {'job':old,'created':False}
    jobs=reconcile(store,{})['jobs']
    cid=target(store)
    if not cid: raise OperationError('no_next_section','No next section to prepare')
    if any(j['status']=='running' for j in jobs): raise OperationError('preparation_busy','Only one preparation may run')
    snapshot=capture(store,cid)
    ready=next((j for j in jobs if j['concept_id']==cid and j['status']=='ready'),None)
    if ready: return {'job':ready,'created':False}
    job={'id':identifier,'concept_id':cid,'snapshot':snapshot,'status':'running','created_at':time.time()}
    save(store,job)
    return {'job':job,'created':True}


def view(store, request):
    jobs=reconcile(store,{'brief':request.get('brief') is True})['jobs']
    cid=request.get('concept_id')
    ready=next((j for j in reversed(jobs) if j['concept_id']==cid and j['status']=='ready'),None)
    return {'jobs':jobs,'next_concept_id':target(store),'ready':ready}

def use(store, request):
    """Record the first teaching turn that received a job's material, so preparation nobody read can be told apart."""
    job = store.get('preparation_jobs', require_text(request, 'id'))
    if job is None:
        raise OperationError('unknown_preparation', request['id'])
    if 'used_by' not in job:
        save(store, {**job, 'used_by': require_text(request, 'turn_id'), 'used_at': time.time()})
    return {'job': brief(store.get('preparation_jobs', job['id']))}


def recover(store, request):
    for job in store.matching('preparation_jobs', 'status', 'running'):
        if store.get('streams',job['id']) is None:
            job.update(status='failed',reason='Preparation startup interrupted; the main teacher will prepare independently')
            save(store,job)
    return reconcile(store,{})

OPERATIONS={'preparation.use':use,'preparation.recover':recover,'preparation.enqueue':enqueue,'preparation.reconcile':reconcile,'preparation.view':view}
