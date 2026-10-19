"""Version-bound preparation material; never learning or interaction evidence."""
import hashlib
import json
import time
from . import curriculum
from .teaching import require_text
from .store import OperationError


def capture(store, cid):
    context = curriculum.context(store, {'concept_id': cid})
    context.pop('position', None)
    data = {'context': context, 'curriculum': curriculum.view(store, {}),
            'sources': store.list('sources')}
    return {'fingerprint': hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest(), 'context':context}


def target(store):
    current = store.get('course','position',{}).get('concept_id')
    if not current: return None
    return curriculum.context(store,{'concept_id':current})['next_concept_id']


def reconcile(store, request):
    current = store.get('course','position',{}).get('concept_id')
    upcoming = target(store)
    for job in store.list('preparation_jobs'):
        if job['status'] not in ('running','ready'): continue
        if job['concept_id'] not in (current,upcoming) or capture(store,job['concept_id'])['fingerprint'] != job['snapshot']['fingerprint']:
            job.update(status='stale',reason='Route or sources changed; the main teacher will prepare independently')
            job.pop('content',None)
        elif job['status']=='running':
            turn=store.get('streams',job['id'])
            if turn and turn['status']=='completed': job.update(status='ready',content=turn['final_text'])
            elif turn and turn['status'] in ('failed','interrupted','paused'):
                job.update(status='deferred' if turn['status']=='paused' else 'failed',reason=turn.get('error','Foreground learning takes priority'))
        store.put('preparation_jobs',job['id'],job)
    return {'jobs':sorted(store.list('preparation_jobs'),key=lambda j:j.get('created_at',0))}


def enqueue(store, request):
    identifier=require_text(request,'id')
    old=store.get('preparation_jobs',identifier)
    if old: return {'job':old,'created':False}
    jobs=reconcile(store,{})['jobs']
    cid=target(store)
    if not cid: raise OperationError('no_next_section','No next section to prepare')
    if any(j['status']=='running' for j in jobs): raise OperationError('preparation_busy','Only one preparation may run')
    snapshot=capture(store,cid)
    ready=next((j for j in jobs if j['concept_id']==cid and j['status']=='ready'),None)
    if ready: return {'job':ready,'created':False}
    job={'id':identifier,'concept_id':cid,'snapshot':snapshot,'status':'running','created_at':time.time()}
    store.put('preparation_jobs',identifier,job)
    return {'job':job,'created':True}


def view(store, request):
    jobs=reconcile(store,{})['jobs']
    cid=request.get('concept_id')
    ready=next((j for j in reversed(jobs) if j['concept_id']==cid and j['status']=='ready'),None)
    return {'jobs':jobs,'next_concept_id':target(store),'ready':ready}

def recover(store, request):
    for job in store.list('preparation_jobs'):
        if job['status']=='running' and store.get('streams',job['id']) is None:
            job.update(status='failed',reason='Preparation startup interrupted; the main teacher will prepare independently')
            store.put('preparation_jobs',job['id'],job)
    return reconcile(store,{})

OPERATIONS={'preparation.recover':recover,'preparation.enqueue':enqueue,'preparation.reconcile':reconcile,'preparation.view':view}
