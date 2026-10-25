"""Evidence records preserve provenance; judgments are supplied by the teacher."""
from .store import OperationError


def required(request, key):
    value = request.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OperationError('invalid_evidence', key + ' must be nonempty text')
    return value


def concept(store, request):
    cid = required(request, 'concept_id')
    if cid not in [c['id'] for c in store.get('curriculum', 'model', {}).get('concepts', [])]:
        raise OperationError('invalid_reference', 'Unknown concept')
    return cid


def interaction(store, iid, role, cid):
    item = store.get('interactions', iid)
    if not item or item['role'] != role or item.get('concept_id') not in (None, cid):
        raise OperationError('invalid_evidence', 'Interaction must match role and concept')
    return item


def immutable(store, namespace, item):
    old = store.get(namespace, item['id'])
    if old and old != item:
        raise OperationError('id_conflict', 'Record ID already has different content')
    return old or store.put(namespace, item['id'], item)


def record(store, request):
    cid = concept(store, request)
    kind = request.get('kind')
    if kind not in ('taught', 'self_report', 'hint', 'demonstrated'):
        raise OperationError('invalid_evidence', 'Unknown evidence kind')
    iid = required(request, 'interaction_id')
    interaction(store, iid, 'user' if kind == 'self_report' else 'assistant', cid)
    item = {'id': required(request, 'id'), 'concept_id': cid, 'kind': kind, 'interaction_id': iid}
    if kind in ('hint', 'demonstrated'):
        item.update({key: required(request, key) for key in ('session_id', 'exercise_id')})
        item['level'] = required(request, 'level') if kind == 'hint' else 'complete_solution'
        if not store.get('evidence', item['id']):
            for assessment in store.list('evidence'):
                if assessment.get('session_id') == item['session_id'] and assessment.get('exercise_id') == item['exercise_id'] and assessment['concept_id'] == cid and 'answer_id' in assessment:
                    if store.get('interactions', iid)['sequence'] <= store.get('interactions', assessment['answer_id'])['sequence']:
                        raise OperationError('invalid_evidence', 'Record assistance before assessing its answer')
    previous = store.get('evidence', item['id'])
    if previous is None or 'source_refs' in previous:
        item['source_refs'] = store.get('interactions', iid).get('source_refs', [])
    return {'evidence': immutable(store, 'evidence', item)}


def view(store, request):
    cid = concept(store, request)
    history = [e for e in store.list('evidence') if e['concept_id'] == cid]
    kinds = {e['kind'] for e in history}
    status = 'retest_passed' if 'retest_passed' in kinds else 'independent' if 'independent' in kinds else 'hinted' if 'hinted' in kinds else 'self_reported' if 'self_report' in kinds else 'taught' if kinds & {'taught', 'demonstrated'} else 'unverified'
    assessments = [e for e in history if 'assessment_id' in e]
    latest = max(assessments, key=lambda e: store.get('interactions', e['assessment_id'])['sequence'], default=None)
    return {'concept_id': cid, 'latest_assessment': latest, 'status': status, 'history': history, 'independently_verified': bool(kinds & {'independent', 'retest_passed'})}


OPERATIONS = {'evidence.record': record, 'evidence.view': view}


def assess(store, request):
    cid = concept(store, request)
    item = {key: required(request, key) for key in ('id', 'session_id', 'exercise_id', 'answer_id', 'assessment_id', 'outcome')}
    if item['outcome'] not in ('passed', 'needs_work'):
        raise OperationError('invalid_evidence', 'Outcome must be passed or needs_work')
    answer = interaction(store, item['answer_id'], 'user', cid)
    assessment = interaction(store, item['assessment_id'], 'assistant', cid)
    if assessment['sequence'] <= answer['sequence']:
        raise OperationError('invalid_evidence', 'Assessment must follow the answer')
    hints = [e for e in store.list('evidence') if e['concept_id'] == cid and e.get('session_id') == item['session_id'] and e.get('exercise_id') == item['exercise_id'] and e['kind'] in ('hint', 'demonstrated') and store.get('interactions', e['interaction_id'])['sequence'] <= answer['sequence']]
    item.update(concept_id=cid, hint_ids=[e['id'] for e in hints], kind='hinted' if hints else 'independent')
    if item['outcome'] != 'passed':
        item['kind'] = 'needs_work'
    previous = store.list('evidence')
    if any(e.get('answer_id') == item['answer_id'] and e['id'] != item['id'] for e in previous):
        raise OperationError('invalid_evidence', 'Answer has already been assessed')
    if request.get('retest_of'):
        item['retest_of'] = required(request, 'retest_of')
        prior = store.get('evidence', item['retest_of'])
        if not prior or prior['concept_id'] != cid or prior['kind'] not in ('independent', 'retest_passed') or prior['session_id'] == item['session_id']:
            raise OperationError('invalid_evidence', 'Retest requires an independent pass in another session')
        if answer['sequence'] <= interaction(store, prior['assessment_id'], 'assistant', cid)['sequence']:
            raise OperationError('invalid_evidence', 'Retest answer must follow prior assessment')
        if item['kind'] == 'independent':
            item['kind'] = 'retest_passed'
    existing = store.get('evidence', item['id'])
    if existing is None or 'answer_source_refs' in existing:
        item['answer_source_refs'] = answer.get('source_refs', [])
        item['assessment_source_refs'] = assessment.get('source_refs', [])
    return {'evidence': immutable(store, 'evidence', item)}

OPERATIONS['evidence.assess'] = assess


def defer(store, request):
    item = {'id': required(request, 'id'), 'concept_id': concept(store, request), 'reason': required(request, 'reason')}
    for field in ('target_concept_id', 'section_id'):
        if field in request:
            item[field] = required(request, field)
    if 'target_concept_id' in item:
        concept(store, {'concept_id': item['target_concept_id']})
    if not ('target_concept_id' in item or 'section_id' in item):
        raise OperationError('invalid_evidence', 'Defer needs a target concept or recap section')
    return {'deferred': immutable(store, 'evidence_deferred', item)}


def review(store, request):
    cid = concept(store, request)
    resolutions = store.list('evidence_resolutions')
    resolved = {r['deferred_id'] for r in resolutions}
    due = [item for item in store.list('evidence_deferred') if item['id'] not in resolved and (item.get('target_concept_id') == cid or (request.get('recap') is True and request.get('section_id') and item.get('section_id') == request['section_id']))]
    return {'evidence': view(store, request), 'due': due, 'deferred_history': store.list('evidence_deferred'), 'resolutions': resolutions, 'quiz_required': False,
            'practice_policy': 'concentrated_at_section_end; minimal_hint_first; full_solution_on_request'}

OPERATIONS.update({'evidence.defer': defer, 'evidence.review': review})


def resolve(store, request):
    item = {k: required(request, k) for k in ('id', 'deferred_id', 'interaction_id')}
    deferred = store.get('evidence_deferred', item['deferred_id'])
    if not deferred:
        raise OperationError('invalid_reference', 'Unknown deferred item')
    confirmation = store.get('interactions', item['interaction_id'])
    allowed_contexts = {None, deferred['concept_id'], deferred.get('target_concept_id')}
    if not confirmation or confirmation['role'] != 'user' or confirmation.get('concept_id') not in allowed_contexts:
        raise OperationError('invalid_evidence', 'Confirmation must be a learner message at the deferred concept or scheduled target')
    return {'resolution': immutable(store, 'evidence_resolutions', item)}

OPERATIONS['evidence.resolve'] = resolve


def unresolved(store, request):
    """Deferred items that no learner confirmation has resolved yet."""
    resolved = {r['deferred_id'] for r in store.list('evidence_resolutions')}
    return {'deferred': [item for item in store.list('evidence_deferred') if item['id'] not in resolved]}

OPERATIONS['evidence.unresolved'] = unresolved
