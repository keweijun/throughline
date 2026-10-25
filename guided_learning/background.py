"""Persistent optional host handoff; derived notes never replace learning evidence."""
import hashlib
import json
from . import curriculum
from .store import OperationError
from .teaching import require_text

STATE_NAMESPACES = ('course', 'curriculum', 'sources', 'interactions', 'evidence', 'evidence_deferred', 'evidence_resolutions', 'sidequestions', 'teaching', 'deferred_explanations')

def fingerprint(store):
    state = {name: store.list(name) for name in STATE_NAMESPACES}
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def handoff_model():
    """The learner's small model, else their teacher model, else the default auxiliary model."""
    from .server.settings import TeacherSettings
    try:
        settings = TeacherSettings().current()
    except OperationError:
        settings = {}
    return settings.get('small_model') or settings.get('model') or 'gpt-6-luna'

def capture(store, spec):
    messages = [store.get('interactions', identifier) for identifier in spec['interaction_ids']]
    if any(message is None for message in messages):
        raise OperationError('invalid_reference', 'Unknown interaction')
    context = curriculum.context(store, {'concept_id': spec['concept_id']}) if spec.get('concept_id') else None
    return {'fingerprint': fingerprint(store), 'interactions': messages, 'context': context}

def enqueue(store, request):
    identifier = require_text(request, 'id')
    ids = request.get('interaction_ids')
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise OperationError('invalid_request', 'interaction_ids must be unique nonempty message IDs')
    spec = {'interaction_ids': ids, 'concept_id': request.get('concept_id')}
    previous = store.get('background_jobs', identifier)
    if previous:
        if previous['spec'] != spec:
            raise OperationError('id_conflict', identifier)
        return {'job': previous}
    job = {'id': identifier, 'spec': spec, 'snapshot': capture(store, spec), 'status': 'queued', 'attempt_ids': []}
    store.put('background_jobs', identifier, job)
    return {'job': job}

def get_job(store, request):
    job = store.get('background_jobs', require_text(request, 'id'))
    if job is None:
        raise OperationError('unknown_job', request['id'])
    return job

def mutate(store, request):
    request_id = require_text(request, 'request_id')
    previous = store.get('background_receipts', request_id)
    if previous:
        if previous['request'] != request:
            raise OperationError('id_conflict', request_id)
        return previous['result']
    job = get_job(store, request)
    op = request['op']
    if op == 'background.pause':
        if job['status'] in ('accepted', 'rejected'):
            raise OperationError('invalid_transition', 'Final jobs cannot be paused')
        job.update(status='paused', reason=require_text(request, 'reason'))
        result = {'job': job}
    elif op == 'background.retry':
        if job['status'] not in ('paused', 'stale', 'rejected'):
            raise OperationError('invalid_transition', 'Pause or finish a failed attempt before retry')
        job.update(status='queued', snapshot=capture(store, job['spec']))
        job.pop('candidate', None)
        job.pop('attempt_id', None)
        result = {'job': job}
    elif op == 'background.claim':
        if job['status'] != 'queued':
            raise OperationError('invalid_transition', 'Only queued jobs can be claimed')
        attempt = require_text(request, 'attempt_id')
        if attempt in job['attempt_ids']:
            raise OperationError('id_conflict', 'Use a new attempt ID after retry')
        job.update(status='running', attempt_id=attempt)
        job['attempt_ids'].append(attempt)
        result = {'job': job, 'handoff': {'model': handoff_model(), **job['snapshot']}, 'model_call_performed': False}
    elif op == 'background.submit':
        if job['status'] != 'running' or request.get('attempt_id') != job.get('attempt_id'):
            raise OperationError('invalid_transition', 'Result must match the current running attempt')
        notes = request.get('notes')
        if not isinstance(notes, list) or not notes:
            raise OperationError('invalid_request', 'notes must be a nonempty list')
        allowed_ids = set(job['spec']['interaction_ids'])
        allowed_refs = (job['snapshot']['context'] or {}).get('sources', [])
        for note in notes:
            if not isinstance(note, dict) or set(note) - {'text', 'interaction_ids', 'source_refs'}:
                raise OperationError('invalid_request', 'Only text and provenance fields are accepted')
            require_text(note, 'text')
            ids = note.get('interaction_ids')
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in allowed_ids for i in ids):
                raise OperationError('invalid_reference', 'Notes must cite handed-off interaction IDs')
            refs = note.get('source_refs', [])
            if not isinstance(refs, list):
                raise OperationError('invalid_reference', 'source_refs must be a list')
            for ref in refs:
                curriculum.source_unit(store, ref)
                if not any(all(ref[k] == allowed[k] for k in ('source_id', 'revision', 'unit_id')) for allowed in allowed_refs):
                    raise OperationError('invalid_reference', 'Notes may cite only handed-off source units')
        job.update(status='candidate' if fingerprint(store) == job['snapshot']['fingerprint'] else 'stale', candidate=notes)
        result = {'job': job}
    elif op == 'background.review':
        if job['status'] != 'candidate':
            raise OperationError('invalid_transition', 'Review requires a candidate')
        decision = request.get('decision')
        if decision not in ('accept', 'reject'):
            raise OperationError('invalid_request', 'decision must be accept or reject')
        job['review_reason'] = require_text(request, 'reason')
        job['status'] = 'accepted' if decision == 'accept' else 'rejected'
        if fingerprint(store) != job['snapshot']['fingerprint']:
            job['status'] = 'stale'
        if job['status'] == 'accepted':
            store.put('derived_notes', job['id'], {'id': job['id'], 'notes': job['candidate'], 'fingerprint': job['snapshot']['fingerprint']})
        result = {'job': job}
    else:
        raise OperationError('unknown_operation', op)
    store.put('background_jobs', job['id'], job)
    store.put('background_receipts', request_id, {'request': request, 'result': result})
    return result

def view(store, request):
    if request.get('id'):
        return {'job': get_job(store, request)}
    return {'jobs': store.list('background_jobs'), 'notes': [{**note, 'stale': note['fingerprint'] != fingerprint(store)} for note in store.list('derived_notes')]}

OPERATIONS = {'background.enqueue': enqueue, 'background.view': view, **{name: mutate for name in ('background.pause', 'background.retry', 'background.claim', 'background.submit', 'background.review')}}
