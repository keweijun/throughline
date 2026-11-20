"""Drill sessions (ADR 0025): review with a fast teacher over the Review place's scope. A session is a conversation,
kept and reopened at will, never finished or due: each teacher turn may add questions, which are review questions
(origin review) answered and assessed as before, so their misses reach the mistakes book and their passes are evidence.
A chapter's drill and a warm-up before a section are sessions with a fixed scope."""
import time

from . import curriculum, review
from .store import OperationError
from .teaching import require_text

SESSIONS = 'drill_sessions'
KINDS = ('drill', 'chapter', 'warm_up')
MAX_MESSAGE = 4000


def _scope(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - {'chapter_ids', 'concept_ids'} or not all(
            isinstance(value.get(k, []), list) and all(isinstance(i, str) for i in value.get(k, [])) for k in ('chapter_ids', 'concept_ids')):
        raise OperationError('invalid_request', 'scope lists chapter_ids and concept_ids')
    return {k: list(dict.fromkeys(value[k])) for k in ('chapter_ids', 'concept_ids') if value.get(k)}


def sections(store, value):
    """The studied sections a session covers, in route order (as a review set's, ADR 0014)."""
    return review.scope_sections(store, value)


def create(store, request):
    """A new session over a scope: everything studied, chosen chapters or sections, one chapter (`chapter`) or the
    studied prerequisites of a section about to be learned (`warm_up`). A scope with nothing studied is refused."""
    identifier = require_text(request, 'id')
    previous = store.get(SESSIONS, identifier)
    if previous:
        return {'session': previous, 'sections': sections(store, previous)}
    kind = request.get('kind', 'drill')
    if kind not in KINDS:
        raise OperationError('invalid_request', 'kind must be drill, chapter or warm_up')
    value = {'id': identifier, 'kind': kind, 'created_at': time.time(), 'turn_ids': []}
    if kind == 'chapter':
        chapter = require_text(request, 'chapter_id')
        if chapter not in {c['id'] for c in curriculum.model(store)['chapters']}:
            raise OperationError('unknown_chapter', chapter)
        value.update(chapter_id=chapter, scope={'chapter_ids': [chapter]})
    elif kind == 'warm_up':
        value['concept_id'] = require_text(request, 'concept_id')
    else:
        scope = _scope(request.get('scope'))
        if scope:
            value['scope'] = scope
    covered = sections(store, value)
    if not covered:
        raise OperationError('nothing_to_review', 'Nothing studied matches this review yet')
    return {'session': store.put(SESSIONS, identifier, value), 'sections': covered}


def _read(store, identifier):
    value = store.get(SESSIONS, identifier)
    if value is None:
        raise OperationError('unknown_session', identifier)
    return value


def add_turn(store, request):
    """Record a teacher turn of the session, in order, with the learner's message that asked for it, if any."""
    value = _read(store, require_text(request, 'id'))
    turn_id = require_text(request, 'turn_id')
    message = request.get('message') or ''
    if not isinstance(message, str) or len(message) > MAX_MESSAGE:
        raise OperationError('invalid_request', f'A message has at most {MAX_MESSAGE} characters')
    if turn_id not in value['turn_ids']:
        value['turn_ids'].append(turn_id)
        if message.strip():
            value.setdefault('messages', {})[turn_id] = message.strip()
        value['updated_at'] = time.time()
        store.put(SESSIONS, value['id'], value)
    return {'session': value}


def add_questions(store, request):
    """The questions a turn wrote, validated as review questions over the session's sections: an invalid recall question
    is dropped, any other invalid question refuses them all (`invalid_review_question`)."""
    from .practice import FormatError, _review_questions
    value = _read(store, require_text(request, 'id'))
    turn_id = require_text(request, 'turn_id')
    if turn_id not in value['turn_ids']:
        raise OperationError('invalid_request', 'The turn is not part of this session')
    existing = [t for t in store.list('practice_tasks') if t.get('drill_turn_id') == turn_id]
    if existing:
        return {'task_ids': [t['id'] for t in existing]}
    try:
        questions = _review_questions(store, {'id': turn_id}, {'questions': request.get('questions')}, allowed=sections(store, value))
    except FormatError as exc:
        raise OperationError('invalid_review_question', str(exc)) from exc
    ids = []
    for index, question in enumerate(questions):
        identifier = f'{turn_id}:{index}'
        store.put('practice_tasks', identifier, {'id': identifier, 'concept_id': question['tests_concept_ids'][0], 'origin': 'review',
                                                 'session_id': value['id'], 'drill_turn_id': turn_id, 'status': 'pending', 'history': [],
                                                 'source_refs': [], 'created_at': time.time(), **question})
        ids.append(identifier)
    return {'task_ids': ids}


def listing(store, _request):
    """Every session, newest first, with its turns and questions in order and the sections it covers."""
    tasks = {}
    for task in store.list('practice_tasks'):
        if task.get('session_id'):
            tasks.setdefault(task['session_id'], []).append(task)
    found = []
    for value in sorted(store.list(SESSIONS), key=lambda s: -s.get('updated_at', s['created_at'])):
        mine = sorted(tasks.get(value['id'], []), key=lambda t: (value['turn_ids'].index(t['drill_turn_id']) if t['drill_turn_id'] in value['turn_ids'] else 0, t['id']))
        found.append({**value, 'sections': sections(store, value), 'task_ids': [t['id'] for t in mine]})
    return {'sessions': found}


OPERATIONS = {'drill.create': create, 'drill.add_turn': add_turn, 'drill.questions': add_questions, 'drill.list': listing}
