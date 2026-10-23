"""Auditable curriculum mappings; teaching judgments remain with the teacher."""
from .store import OperationError

def view(store, request):
    return store.get('curriculum', 'model', {'concepts': [], 'route': [], 'coverage': []})

def source_unit(store, ref):
    if not isinstance(ref, dict) or any(not isinstance(ref.get(k), str) for k in ('source_id', 'revision', 'unit_id')):
        raise OperationError('invalid_reference', 'Source reference requires source_id, revision and unit_id')
    snapshot = store.get('source_revisions', ref['source_id'] + ':' + ref['revision'])
    if snapshot:
        for unit in snapshot['units']:
            if unit['id'] == ref['unit_id']:
                return unit
    raise OperationError('invalid_reference', 'Unknown source revision or unit')

def save(store, request):
    model = {key: request.get(key, []) for key in ('concepts', 'route', 'coverage')}
    if any(not isinstance(model[k], list) for k in model):
        raise OperationError('invalid_request', 'concepts, route and coverage must be arrays')
    concepts = {}
    for concept in model['concepts']:
        if not isinstance(concept, dict) or not isinstance(concept.get('id'), str) or not concept['id'] or not isinstance(concept.get('title'), str):
            raise OperationError('invalid_request', 'Concept requires nonempty id and title')
        if concept['id'] in concepts:
            raise OperationError('invalid_request', 'Duplicate concept id')
        for field in ('prerequisites', 'links', 'notations', 'exercises'):
            if not isinstance(concept.get(field, []), list):
                raise OperationError('invalid_request', field + ' must be an array')
        if any(not isinstance(cid, str) for cid in concept.get('prerequisites', [])):
            raise OperationError('invalid_reference', 'Prerequisite IDs must be strings')
        concepts[concept['id']] = concept
        for field in ('links', 'notations', 'exercises'):
            for ref in concept.get(field, []):
                source_unit(store, ref)
    for concept in concepts.values():
        if any(p not in concepts for p in concept.get('prerequisites', [])):
            raise OperationError('invalid_reference', 'Unknown prerequisite')
    visiting, done = set(), set()
    def visit(cid):
        if cid in visiting:
            raise OperationError('prerequisite_cycle', cid)
        if cid in done:
            return
        visiting.add(cid)
        for prerequisite in concepts[cid].get('prerequisites', []):
            visit(prerequisite)
        visiting.remove(cid)
        done.add(cid)
    for cid in concepts:
        visit(cid)
    route = model['route']
    if any(not isinstance(cid, str) for cid in route) or len(set(route)) != len(route) or set(route) != set(concepts):
        raise OperationError('invalid_route', 'Route must contain every concept exactly once')
    for cid in route:
        if any(route.index(p) >= route.index(cid) for p in concepts[cid].get('prerequisites', [])):
            raise OperationError('invalid_route', 'Prerequisites must precede their dependents')
    seen = set()
    for entry in model['coverage']:
        source_unit(store, entry)
        key = (entry['source_id'], entry['revision'], entry['unit_id'])
        if key in seen:
            raise OperationError('invalid_coverage', 'Duplicate unit mapping')
        seen.add(key)
        if not isinstance(entry.get('concept_ids', []), list) or any(not isinstance(cid, str) for cid in entry.get('concept_ids', [])):
            raise OperationError('invalid_coverage', 'concept_ids must be an array of strings')
        disposition = entry.get('disposition')
        if disposition not in ('mapped', 'deferred', 'needs_review'):
            raise OperationError('invalid_coverage', 'Unknown disposition')
        if disposition == 'mapped' and not entry.get('concept_ids'):
            raise OperationError('invalid_coverage', 'Mapped units require concept_ids')
        if disposition != 'mapped' and not str(entry.get('reason', '')).strip():
            raise OperationError('invalid_coverage', 'Deferred/review units require a reason')
        if entry.get('verification', 'pending') not in ('pending', 'verified'):
            raise OperationError('invalid_coverage', 'Unknown verification')
        if entry.get('verification') == 'verified' and not str(entry.get('verification_note', '')).strip():
            raise OperationError('invalid_coverage', 'Verification requires a review note')
        if any(cid not in concepts for cid in entry.get('concept_ids', [])):
            raise OperationError('invalid_reference', 'Unknown coverage concept')
        if disposition == 'mapped':
            if is_stale(store, entry):
                raise OperationError('invalid_coverage', 'Mapped coverage must reference a currently readable revision')
            for cid in entry['concept_ids']:
                if not any(all(ref.get(k) == entry[k] for k in ('source_id', 'revision', 'unit_id')) for ref in concepts[cid].get('links', [])):
                    raise OperationError('invalid_coverage', 'Mapped concept must link the same source unit')
    previous = view(store, request)
    previous_ids = set(previous['route'])
    if not previous_ids.issubset(concepts):
        raise OperationError('invalid_route', 'Preserve stable concept IDs; defer content instead of deleting it')
    if [cid for cid in route if cid in previous_ids] != previous['route'] and request.get('confirm_reorder') is not True:
        raise OperationError('confirmation_required', 'Changing the relative order of existing concepts requires user confirmation')
    store.put('curriculum', 'model', model)
    return model

def coverage(store, request):
    model = view(store, request)
    units = []
    for source in store.list('sources'):
        snapshot = store.get('source_revisions', source['id'] + ':' + str(source['revision']), {'units': []})
        for unit in snapshot['units']:
            ref = {'source_id': source['id'], 'revision': source['revision'], 'unit_id': unit['id']}
            mapping = next((item for item in model['coverage'] if all(item.get(k) == v for k, v in ref.items())), {})
            prior = next((item for item in model['coverage'] if item['source_id'] == source['id'] and item['unit_id'] == unit['id'] and item['revision'] != source['revision']), None)
            if not mapping and prior:
                mapping = {'disposition': 'needs_review', 'reason': 'Source revision changed', 'verification': 'pending', 'concept_ids': prior.get('concept_ids', [])}
            if source['status'] == 'failed' or unit.get('status') in ('failed', 'needs_review'):
                mapping = {**mapping, 'disposition': 'needs_review', 'reason': 'Source extraction requires review', 'verification': 'pending'}
            units.append({**ref, 'locator': unit['locator'], 'disposition': mapping.get('disposition', 'unmapped'), 'concept_ids': mapping.get('concept_ids', []), 'reason': mapping.get('reason', ''), 'verification': mapping.get('verification', 'pending'), 'verification_note': mapping.get('verification_note', '')})
    return {'units': units, 'stale_mappings': [entry for entry in model['coverage'] if is_stale(store, entry)], 'sources': store.list('sources'), 'semantic_completeness': 'requires_teacher_review'}

def verify(store, request):
    reviews = request.get('reviews')
    if not isinstance(reviews, list) or not reviews:
        raise OperationError('invalid_request', 'reviews must be a nonempty array')
    model = view(store, request)
    seen, applied = set(), []
    for review in reviews:
        unit = source_unit(store, review)
        key = (review['source_id'], review['revision'], review['unit_id'])
        if key in seen:
            raise OperationError('invalid_review', 'Duplicate review')
        seen.add(key)
        applied.append(dict(zip(('source_id', 'revision', 'unit_id'), key)))
        if review.get('verification') not in ('pending', 'verified'):
            raise OperationError('invalid_review', 'Unknown verification')
        if not str(review.get('verification_note', '')).strip():
            raise OperationError('invalid_review', 'A review requires a note describing what was compared')
        if is_stale(store, review):
            raise OperationError('invalid_review', 'Review the currently registered revision')
        if review['verification'] == 'verified' and unit.get('status', 'read') != 'read':
            raise OperationError('invalid_review', 'Extraction failed or is empty; re-register or map this unit instead')
        entry = next((item for item in model['coverage'] if all(item.get(k) == v for k, v in zip(('source_id', 'revision', 'unit_id'), key))), None)
        if entry is None:
            concept_ids = [c['id'] for c in model['concepts'] if any(all(ref.get(k) == v for k, v in zip(('source_id', 'revision', 'unit_id'), key)) for ref in c.get('links', []))]
            if not concept_ids:
                raise OperationError('invalid_review', 'Unit has no coverage mapping or concept link')
            entry = {'source_id': key[0], 'revision': key[1], 'unit_id': key[2], 'disposition': 'mapped', 'concept_ids': concept_ids}
            model['coverage'].append(entry)
        entry.update(verification=review['verification'], verification_note=str(review['verification_note']).strip())
    store.put('curriculum', 'model', model)
    return {'reviewed': applied}

def is_stale(store, ref):
    source = store.get('sources', ref['source_id'], {})
    return source.get('revision') != ref['revision'] or source.get('status') == 'failed'

def context(store, request):
    model = view(store, request)
    position = store.get('course', 'position', {})
    concept_id = request.get('concept_id', position.get('concept_id'))
    concepts = {c['id']: c for c in model['concepts']}
    if concept_id not in concepts:
        raise OperationError('unknown_concept', str(concept_id))
    concept = concepts[concept_id]
    index = model['route'].index(concept_id)
    return {'concept': concept, 'position': position, 'prerequisites': [concepts[c] for c in concept.get('prerequisites', [])], 'next_concept_id': model['route'][index + 1] if index + 1 < len(model['route']) else None, 'sources': [linked_unit(store, ref, model) for ref in concept.get('links', [])]}

def linked_unit(store, ref, model):
    mapping = next((item for item in model['coverage'] if all(item.get(k) == ref.get(k) for k in ('source_id', 'revision', 'unit_id'))), {})
    return {**ref, **source_unit(store, ref), 'stale': is_stale(store, ref),
            'verification': mapping.get('verification', 'pending'), 'verification_note': mapping.get('verification_note', '')}

OPERATIONS = {'curriculum.save': save, 'curriculum.view': view, 'curriculum.coverage': coverage, 'curriculum.verify': verify, 'curriculum.context': context}
