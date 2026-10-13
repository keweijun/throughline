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
    position = store.get('course', 'position') or {}
    focused = curriculum.context(store, {}) if position.get('concept_id') in curriculum.view(store, {})['route'] else None
    return {'position': store.get('course', 'position'), 'context': focused, 'active_branch': active_branch(store), 'due_explanations': due(store), 'unanswered_questions': [item for item in store.list('sidequestions') if not item.get('answer_interaction_id')], 'recent_interactions': recent[-limit:] if limit else []}

OPERATIONS = {'interaction.record': record_interaction, 'session.resume': resume}

def interaction(store, identifier, role):
    value = store.get('interactions', identifier)
    if value is None or value['role'] != role:
        raise OperationError('invalid_interaction', 'Expected a recorded ' + role + ' interaction')
    return value

def active_branch(store):
    identifier = store.get('teaching', 'active_branch')
    return store.get('sidequestions', identifier) if identifier else None

def enter(store, request):
    concept_id = require_text(request, 'concept_id')
    validate_concept(store, concept_id)
    if active_branch(store):
        raise OperationError('active_branch', 'Continue or answer the active sidequestion first')
    position = {'concept_id': concept_id, 'goal': require_text(request, 'goal'), 'next_step': require_text(request, 'next_step'), 'progress': request.get('progress', '')}
    store.put('course', 'position', position)
    return {'position': position, 'due_explanations': due(store)}

def open_question(store, request):
    identifier = require_text(request, 'id')
    question = interaction(store, request.get('interaction_id'), 'user')
    category, depth = request.get('category'), request.get('depth')
    if category not in ('local', 'prerequisite', 'future', 'repeated', 'extension') or depth not in ('short', 'long'):
        raise OperationError('invalid_request', 'Provide a supported category and short/long depth')
    rationale = require_text(request, 'rationale')
    strategy = require_text(request, 'strategy')
    if category == 'repeated' and strategy not in ('new_example', 'concept_bridge', 'alternative_representation'):
        raise OperationError('invalid_strategy', 'Repeated confusion requires a new example, concept bridge or alternative representation')
    decision = {'interaction_id': question['id'], 'category': category, 'depth': 'long' if request.get('explicit_deepen') is True else depth, 'explicit_deepen': request.get('explicit_deepen') is True, 'rationale': rationale, 'strategy': strategy}
    target = request.get('target_concept_id')
    if category == 'future':
        validate_concept(store, target)
    decision['target_concept_id'] = target
    previous = store.get('sidequestions', identifier)
    if previous:
        if any(previous[k] != v for k, v in decision.items()):
            raise OperationError('id_conflict', identifier)
        return {'branch': previous}
    if active_branch(store):
        raise OperationError('active_branch', 'Resolve or continue the current sidequestion before opening another')
    position = store.get('course', 'position')
    if not position:
        raise OperationError('missing_mainline', 'Enter a mainline before a sidequestion')
    value = {'id': identifier, **decision, 'restore_point': position, 'status': 'open'}
    store.put('sidequestions', identifier, value)
    store.put('teaching', 'active_branch', identifier)
    return {'branch': value}

def get_branch(store, request):
    branch = store.get('sidequestions', require_text(request, 'id'))
    if branch is None:
        raise OperationError('unknown_branch', request['id'])
    return branch

def answer(store, request):
    branch = get_branch(store, request)
    answer_value = interaction(store, request.get('answer_interaction_id'), 'assistant')
    if answer_value['sequence'] <= interaction(store, branch['interaction_id'], 'user')['sequence']:
        raise OperationError('invalid_interaction', 'Answer must follow the question')
    if branch.get('answer_interaction_id'):
        if branch['answer_interaction_id'] != answer_value['id']:
            raise OperationError('id_conflict', branch['id'])
        return {'branch': branch}
    if branch['status'] != 'open':
        raise OperationError('invalid_transition', 'Only an open question can be answered')
    if branch['category'] == 'future' and branch['depth'] == 'short':
        store.put('deferred_explanations', branch['id'], {'id': branch['id'], 'interaction_id': branch['interaction_id'], 'target_concept_id': branch['target_concept_id'], 'provisional_answer_interaction_id': answer_value['id'], 'status': 'pending'})
    branch['answer_interaction_id'] = answer_value['id']
    branch['status'] = 'resumed' if branch['depth'] == 'short' else 'waiting'
    store.put('sidequestions', branch['id'], branch)
    if branch['status'] == 'resumed':
        store.delete('teaching', 'active_branch')
        store.put('course', 'position', branch['restore_point'])
    return {'branch': branch}

def continue_mainline(store, request):
    branch = get_branch(store, request)
    if branch['status'] == 'resumed':
        return {'branch': branch}
    branch['status'] = 'resumed'
    branch['continued_by_user'] = True
    store.put('sidequestions', branch['id'], branch)
    store.delete('teaching', 'active_branch')
    store.put('course', 'position', branch['restore_point'])
    return {'branch': branch}

OPERATIONS.update({'mainline.enter': enter, 'sidequestion.open': open_question, 'sidequestion.answer': answer, 'sidequestion.continue': continue_mainline})


def due(store):
    position = store.get('course', 'position', {})
    return [item for item in store.list('deferred_explanations') if item['status'] == 'pending' and item['target_concept_id'] == position.get('concept_id')]

def resolve_deferred(store, request):
    item = store.get('deferred_explanations', require_text(request, 'id'))
    if item is None:
        raise OperationError('unknown_deferred', request['id'])
    answer_value = interaction(store, request.get('answer_interaction_id'), 'assistant')
    if answer_value['sequence'] <= interaction(store, item['provisional_answer_interaction_id'], 'assistant')['sequence']:
        raise OperationError('invalid_interaction', 'Full explanation must follow provisional answer')
    if item['status'] == 'resolved' and item.get('answer_interaction_id') != answer_value['id']:
        raise OperationError('id_conflict', item['id'])
    item['status'] = 'resolved'
    item['answer_interaction_id'] = answer_value['id']
    store.put('deferred_explanations', item['id'], item)
    return {'deferred_explanation': item}

OPERATIONS['deferred.resolve'] = resolve_deferred
