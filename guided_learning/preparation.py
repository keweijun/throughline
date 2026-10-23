"""Version-bound preparation material; never learning or interaction evidence."""
import hashlib
import json
import re
import time
from pathlib import Path
from . import curriculum
from .teaching import require_text
from .store import OperationError
from .preferences import view as preferences


def capture(store, cid):
    context = curriculum.context(store, {'concept_id': cid})
    context.pop('position', None)
    language = preferences(store,{})['preferences']['language']
    model = curriculum.view(store, {})
    # Coverage and verification record source reviews, not teaching content; reviewing must not discard material.
    sources = [{k:v for k,v in s.items() if k not in ('verification','verification_note')} for s in context['sources']]
    data = {'context': {**context, 'sources': sources}, 'curriculum': {k: model[k] for k in ('concepts','route')}, 'language': language,
            'sources': store.list('sources')}
    return {'fingerprint': hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest(), 'context':context, 'language':language}


REVIEW_LIMIT = 8
REVIEW_BLOCK = re.compile(r'<source-review>(.*?)</source-review>', re.S)
KEY = ('source_id','revision','unit_id')


def target(store):
    current = store.get('course','position',{}).get('concept_id')
    if not current:
        route = curriculum.view(store,{})['route']
        return route[0] if route else None
    return curriculum.context(store,{'concept_id':current})['next_concept_id']


def review_targets(store, context):
    """Linked units of the section still pending verification whose extraction succeeded."""
    targets = []
    for source in context['sources']:
        if source['verification'] == 'verified' or source['stale'] or source.get('status','read') != 'read':
            continue
        kind = 'pdf' if Path(store.get('sources',source['source_id'],{}).get('path','')).suffix.lower() == '.pdf' else 'markdown'
        targets.append({**{k:source[k] for k in KEY},'kind':kind})
    return targets[:REVIEW_LIMIT]


def apply_review(store, job, text):
    """Records the teacher's reviews of this job's own targets; PDF pages count only if their image was attached."""
    blocks = REVIEW_BLOCK.findall(text)
    content = REVIEW_BLOCK.sub('', text).strip()
    allowed = [{k:t[k] for k in KEY} for t in job.get('review',[]) if t['kind'] == 'markdown' or {k:t[k] for k in KEY} in job.get('attached',[])]
    result = {'verified':[],'pending':[],'ignored':0}
    try:
        reviews = json.loads(blocks[-1])['reviews'] if blocks else []
        if not isinstance(reviews,list): reviews = []
    except (ValueError,TypeError,KeyError):
        reviews, result['error'] = [], 'Unreadable source review'
    for review in reviews:
        ref = {k:review.get(k) for k in KEY} if isinstance(review,dict) else None
        if ref not in allowed:
            result['ignored'] += 1
            continue
        allowed.remove(ref)
        try:
            curriculum.verify(store,{'reviews':[{**ref,'verification':review.get('verification'),'verification_note':review.get('verification_note','')}]})
            result[review['verification']].append(ref)
        except OperationError:
            result['ignored'] += 1
    return content, result


def reconcile(store, request):
    current = store.get('course','position',{}).get('concept_id')
    upcoming = target(store)
    for job in store.list('preparation_jobs'):
        if job['status'] not in ('running','ready'): continue
        if job['concept_id'] not in (current,upcoming) or capture(store,job['concept_id'])['fingerprint'] != job['snapshot']['fingerprint']:
            job.update(status='stale',reason='Route, sources, or teaching language changed; the main teacher will prepare independently')
            job.pop('content',None)
        elif job['status']=='running':
            turn=store.get('streams',job['id'])
            if turn and turn['status']=='completed':
                content, review = apply_review(store, job, turn['final_text'])
                job.update(status='ready',content=content,review_result=review)
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
    job={'id':identifier,'concept_id':cid,'snapshot':snapshot,'status':'running','created_at':time.time(),
         'review':review_targets(store,snapshot['context'])}
    store.put('preparation_jobs',identifier,job)
    return {'job':job,'created':True}


def view(store, request):
    jobs=reconcile(store,{})['jobs']
    cid=request.get('concept_id')
    ready=next((j for j in reversed(jobs) if j['concept_id']==cid and j['status']=='ready'),None)
    return {'jobs':jobs,'next_concept_id':target(store),'ready':ready}

def attach(store, request):
    """Records which review targets the host attached as original page images."""
    job=store.get('preparation_jobs',require_text(request,'id'))
    if not job or job['status']!='running': raise OperationError('unknown_job','No running preparation job')
    attached=request.get('attached',[])
    targets=[{k:t[k] for k in KEY} for t in job.get('review',[])]
    if not isinstance(attached,list) or any(not isinstance(a,dict) or {k:a.get(k) for k in KEY} not in targets for a in attached):
        raise OperationError('invalid_request','attached must list review targets')
    job['attached']=[{k:a[k] for k in KEY} for a in attached]
    store.put('preparation_jobs',job['id'],job)
    return {'job':job}

def recover(store, request):
    for job in store.list('preparation_jobs'):
        if job['status']=='running' and store.get('streams',job['id']) is None:
            job.update(status='failed',reason='Preparation startup interrupted; the main teacher will prepare independently')
            store.put('preparation_jobs',job['id'],job)
    return reconcile(store,{})

OPERATIONS={'preparation.recover':recover,'preparation.attach':attach,'preparation.enqueue':enqueue,'preparation.reconcile':reconcile,'preparation.view':view}
