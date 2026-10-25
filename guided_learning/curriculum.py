"""Auditable curriculum mappings; teaching judgments remain with the teacher."""
from .store import OperationError

def view(store, request):
    return {'chapters': [], **store.get('curriculum', 'model', {'concepts': [], 'route': [], 'coverage': []})}

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
    # Omitting chapters keeps the current grouping; new concepts must then be placed through chapters.
    model['chapters'] = request['chapters'] if 'chapters' in request else view(store, request)['chapters']
    return store_model(store, model, request.get('confirm_reorder') is True)

def store_model(store, model, confirm_reorder):
    if any(not isinstance(model[k], list) for k in model):
        raise OperationError('invalid_request', 'concepts, route, coverage and chapters must be arrays')
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
    model['chapters'] = chapters = [validate_chapter(c) for c in model['chapters']]
    if len({c['id'] for c in chapters}) != len(chapters):
        raise OperationError('invalid_chapters', 'Duplicate chapter id')
    if chapters and [cid for c in chapters for cid in c['concept_ids']] != route:
        raise OperationError('invalid_chapters', 'Chapters must list every route concept exactly once, in route order')
    previous = view(store, {})
    previous_ids = set(previous['route'])
    if not previous_ids.issubset(concepts):
        raise OperationError('invalid_route', 'Preserve stable concept IDs; defer content instead of deleting it')
    previous_chapters = [c['id'] for c in previous['chapters']]
    reordered = [cid for cid in route if cid in previous_ids] != previous['route']
    reordered = reordered or [c['id'] for c in chapters if c['id'] in previous_chapters] != [c for c in previous_chapters if c in {c['id'] for c in chapters}]
    if reordered and not confirm_reorder:
        raise OperationError('confirmation_required', 'Changing the relative order of existing concepts or chapters requires user confirmation')
    store.put('curriculum', 'model', model)
    return model

def validate_chapter(chapter):
    if not isinstance(chapter, dict) or not isinstance(chapter.get('id'), str) or not chapter['id'] or not isinstance(chapter.get('title'), str) or not chapter['title'].strip():
        raise OperationError('invalid_chapters', 'Chapter requires nonempty id and title')
    if not isinstance(chapter.get('summary', ''), str):
        raise OperationError('invalid_chapters', 'Chapter summary must be a string')
    ids = chapter.get('concept_ids', [])
    if not isinstance(ids, list) or any(not isinstance(cid, str) for cid in ids):
        raise OperationError('invalid_chapters', 'Chapter concept_ids must be an array of strings')
    return {'id': chapter['id'], 'title': chapter['title'], **({'summary': chapter['summary']} if chapter.get('summary') else {}), 'concept_ids': ids}

def outline(store, request):
    """Set the ordered chapters; existing chapters keep their concepts unless concept_ids reassigns existing concepts."""
    previous = view(store, request)
    if not isinstance(request.get('chapters'), list) or not request['chapters']:
        raise OperationError('invalid_chapters', 'Outline requires a nonempty chapters array')
    current = {c['id']: c for c in previous['chapters']}
    chapters = []
    for chapter in request['chapters']:
        if not isinstance(chapter, dict):
            raise OperationError('invalid_chapters', 'Chapter must be an object')
        kept = current.get(chapter.get('id'), {})
        chapters.append({**kept, **chapter, 'concept_ids': chapter.get('concept_ids', kept.get('concept_ids', []))})
    placed = {cid for c in chapters if isinstance(c['concept_ids'], list) for cid in c['concept_ids']}
    if any(cid not in placed for cid in previous['route']):
        raise OperationError('invalid_chapters', 'Every existing concept needs a chapter; assign them with concept_ids')
    route = [cid for c in chapters for cid in c['concept_ids']] if all(isinstance(c['concept_ids'], list) for c in chapters) else []
    return store_model(store, {**previous, 'route': route, 'chapters': chapters}, request.get('confirm_reorder') is True)

def chapter_save(store, request):
    """Replace one chapter's concepts, in teaching order, and upsert the coverage entries it sends."""
    previous = view(store, request)
    chapter_id = request.get('chapter_id')
    if chapter_id not in [c['id'] for c in previous['chapters']]:
        raise OperationError('unknown_chapter', 'Add the chapter with curriculum.outline first')
    concepts, coverage = request.get('concepts'), request.get('coverage', [])
    if not isinstance(concepts, list) or not isinstance(coverage, list) or any(not isinstance(c, dict) for c in concepts + coverage):
        raise OperationError('invalid_request', 'concepts and coverage must be arrays of objects')
    ids = [c.get('id') for c in concepts]
    chapters = []
    for chapter in previous['chapters']:
        if chapter['id'] == chapter_id:
            chapter = {**chapter, **{k: request[k] for k in ('title', 'summary') if k in request}, 'concept_ids': ids}
        else:
            # Listing a concept from another chapter moves it here.
            chapter = {**chapter, 'concept_ids': [cid for cid in chapter['concept_ids'] if cid not in ids]}
        chapters.append(chapter)
    merged = {entry_key(e): e for e in previous['coverage']}
    for entry in coverage:
        key = entry_key(entry)
        merged[key] = merge_entry(merged.get(key), entry, set(ids))
    model = {'concepts': [c for c in previous['concepts'] if c['id'] not in ids] + concepts,
             'route': [cid for c in chapters for cid in c['concept_ids']], 'coverage': list(merged.values()), 'chapters': chapters}
    return store_model(store, model, request.get('confirm_reorder') is True)

def entry_key(entry):
    return tuple(entry.get(k) for k in ('source_id', 'revision', 'unit_id'))

def merge_entry(existing, entry, chapter_ids):
    """A source unit can serve several chapters: keep the other chapters' concepts on it, mapped if any chapter maps it."""
    others = [cid for cid in (existing or {}).get('concept_ids', []) if cid not in chapter_ids]
    if not others:
        return entry
    merged = {**entry, 'disposition': 'mapped', 'concept_ids': others + [cid for cid in entry.get('concept_ids', []) if cid not in others]}
    merged.pop('reason', None)
    both_verified = existing.get('verification') == 'verified' and entry.get('verification') == 'verified'
    merged['verification'] = 'verified' if both_verified else 'pending'
    if both_verified:
        merged['verification_note'] = existing.get('verification_note', '') + '\n' + entry.get('verification_note', '')
    else:
        merged.pop('verification_note', None)
    return merged

def chapter_view(store, request):
    model = view(store, request)
    index = next((i for i, c in enumerate(model['chapters']) if c['id'] == request.get('chapter_id')), None)
    if index is None:
        raise OperationError('unknown_chapter', str(request.get('chapter_id')))
    chapter = model['chapters'][index]
    ids = set(chapter['concept_ids'])
    linked = {entry_key(r) for c in model['concepts'] if c['id'] in ids for r in c.get('links', [])}
    return {'chapter': chapter, 'index': index, 'chapters': [{'id': c['id'], 'title': c['title']} for c in model['chapters']],
            'concepts': [c for cid in chapter['concept_ids'] for c in model['concepts'] if c['id'] == cid],
            'coverage': [e for e in model['coverage'] if ids & set(e.get('concept_ids', [])) or entry_key(e) in linked]}

def chapter_of(model, concept_id):
    index = next((i for i, c in enumerate(model['chapters']) if concept_id in c['concept_ids']), None)
    return None if index is None else {**model['chapters'][index], 'index': index, 'total': len(model['chapters'])}

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
            units.append({**ref, 'locator': unit['locator'], 'disposition': mapping.get('disposition', 'unmapped'), 'concept_ids': mapping.get('concept_ids', []), 'reason': mapping.get('reason', ''), 'verification': mapping.get('verification', 'pending')})
    return {'units': units, 'stale_mappings': [entry for entry in model['coverage'] if is_stale(store, entry)], 'sources': store.list('sources'), 'semantic_completeness': 'requires_teacher_review'}

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
    return {'concept': concept, 'chapter': chapter_of(model, concept_id), 'position': position, 'prerequisites': [concepts[c] for c in concept.get('prerequisites', [])], 'next_concept_id': model['route'][index + 1] if index + 1 < len(model['route']) else None, 'sources': [{**ref, **source_unit(store, ref), 'stale': is_stale(store, ref)} for ref in concept.get('links', [])]}

OPERATIONS = {'curriculum.save': save, 'curriculum.view': view, 'curriculum.coverage': coverage, 'curriculum.context': context,
              'curriculum.outline': outline, 'curriculum.chapter.save': chapter_save, 'curriculum.chapter.view': chapter_view}
