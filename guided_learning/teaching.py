"""Persist teacher decisions without pretending to infer teaching semantics."""
from . import curriculum
from .store import OperationError

def require_text(request, key):
    value = request.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OperationError('invalid_request', key + ' must be a nonempty string')
    return value

def validate_concept(store, concept_id):
    if concept_id not in curriculum.view(store, {})['route']:
        raise OperationError('unknown_concept', str(concept_id))

def record_interaction(store, request):
    identifier = require_text(request, 'id')
    text = require_text(request, 'text')
    role = request.get('role')
    if role not in ('user', 'assistant'):
        raise OperationError('invalid_request', 'role must be user or assistant')
    concept_id = request.get('concept_id')
    if concept_id is not None:
        validate_concept(store, concept_id)
    value = {'id': identifier, 'role': role, 'text': text, 'concept_id': concept_id}
    previous = store.get('interactions', identifier)
    if previous:
        if any(previous[k] != v for k, v in value.items()):
            raise OperationError('id_conflict', identifier)
        return {'interaction': previous}
    value['sequence'] = max((item['sequence'] for item in store.list('interactions')), default=0) + 1
    store.put('interactions', identifier, value)
    return {'interaction': value}

def resume(store, request):
    limit = request.get('recent_limit', 8)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= 20:
        raise OperationError('invalid_request', 'recent_limit must be between 0 and 20')
    recent = sorted(store.list('interactions'), key=lambda item: item['sequence'])
    return {'position': store.get('course', 'position'), 'recent_interactions': recent[-limit:] if limit else []}

OPERATIONS = {'interaction.record': record_interaction, 'session.resume': resume}
