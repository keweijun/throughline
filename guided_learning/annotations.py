"""Learner annotations: highlights, notes and bookmarks. The learner's own records, never teaching data or evidence."""
import time
from .store import OperationError
from .teaching import require_text, validate_concept

KINDS = ('highlight', 'note', 'bookmark')
MAX_NOTE = 4000
MAX_PASSAGE = 4000


def _text(request, key, limit):
    value = request.get(key, '')
    if not isinstance(value, str):
        raise OperationError('invalid_request', key + ' must be a string')
    value = value.strip()
    if len(value) > limit:
        raise OperationError('invalid_request', f'{key} is longer than {limit} characters')
    return value


def _source(request):
    source = request.get('source')
    if source is None:
        return None
    if not isinstance(source, dict):
        raise OperationError('invalid_request', 'source must be an object')
    ref = {key: require_text(source, key) for key in ('source_id', 'revision', 'unit_id')}
    if isinstance(source.get('label'), str):
        ref['label'] = source['label']
    if isinstance(source.get('page'), int) and source['page'] > 0:
        ref['page'] = source['page']
    return ref


def list_annotations(store, request):
    items = sorted(store.list('annotations'), key=lambda a: a['created_at'])
    if request.get('concept_id'):
        items = [a for a in items if a['concept_id'] == request['concept_id']]
    return {'annotations': items}


def save(store, request):
    identifier = require_text(request, 'id')
    previous = store.get('annotations', identifier)
    note = _text(request, 'note', MAX_NOTE)
    if previous:
        # Only the note changes after creation; where an annotation points is fixed.
        updated = {**previous, 'note': note, 'updated_at': time.time()}
        if updated['kind'] == 'note' and not note:
            raise OperationError('invalid_request', 'A note needs text')
        return {'annotation': store.put('annotations', identifier, updated)}
    kind = request.get('kind')
    if kind not in KINDS:
        raise OperationError('invalid_request', 'kind must be highlight, note or bookmark')
    passage = _text(request, 'passage', MAX_PASSAGE)
    turn_id, task_id = request.get('turn_id'), request.get('task_id')
    source = _source(request)
    concept_id = request.get('concept_id')
    # A lesson, side-question answer or exercise already belongs to a section, so that section wins.
    if turn_id is not None:
        turn = store.get('streams', turn_id) if isinstance(turn_id, str) else None
        if not turn or turn['channel'] not in ('mainline', 'sidequestion'):
            raise OperationError('invalid_request', 'turn_id must be a lesson or a side-question answer')
        concept_id = turn.get('concept_id') or concept_id
    if task_id is not None:
        task = store.get('practice_tasks', task_id) if isinstance(task_id, str) else None
        if not task:
            raise OperationError('invalid_request', 'task_id must be an exercise')
        concept_id = task['concept_id']
    concept_id = require_text({'concept_id': concept_id}, 'concept_id')
    validate_concept(store, concept_id)
    anchors = sum(anchor is not None for anchor in (turn_id, task_id, source))
    if kind == 'highlight' and (not passage or anchors != 1):
        raise OperationError('invalid_request', 'A highlight needs a passage in one lesson, answer, exercise or source')
    if anchors > 1:
        raise OperationError('invalid_request', 'An annotation points to at most one place')
    if kind == 'note' and not note:
        raise OperationError('invalid_request', 'A note needs text')
    if kind == 'bookmark' and passage:
        raise OperationError('invalid_request', 'A bookmark has no passage; highlight it instead')
    # A passage can repeat in its text; this says which repeat was marked. Records without it mean the first.
    occurrence = request.get('occurrence', 0)
    if not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 0 or (occurrence and not passage):
        raise OperationError('invalid_request', 'occurrence must be a non-negative integer, for a passage')
    now = time.time()
    annotation = {'id': identifier, 'kind': kind, 'concept_id': concept_id, 'turn_id': turn_id, 'task_id': task_id, 'source': source,
                  'passage': passage, 'occurrence': occurrence, 'note': note, 'created_at': now, 'updated_at': now}
    return {'annotation': store.put('annotations', identifier, annotation)}


def delete(store, request):
    identifier = require_text(request, 'id')
    if store.get('annotations', identifier) is None:
        raise OperationError('unknown_annotation', identifier)
    store.delete('annotations', identifier)
    return {'deleted': identifier}


OPERATIONS = {'annotations.list': list_annotations, 'annotations.save': save, 'annotations.delete': delete}
