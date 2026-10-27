"""Stepped lessons (ADR 0009): a section's lesson is taught as lesson steps, one mainline turn each, following a plan
the teacher may revise as it teaches. Lessons saved before this module are single turns with no record here."""
import time
from .store import OperationError
from .teaching import require_text, validate_concept

MAX_STEPS = 8  # the whole plan: about three steps, plus room for bridges
MAX_TITLE = 200


def _title(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_TITLE:
        raise OperationError('invalid_plan', f'A step title must be text of at most {MAX_TITLE} characters')
    return value.strip()


def _read(store, identifier):
    lesson = store.get('lessons', identifier)
    if lesson is None:
        raise OperationError('unknown_lesson', identifier)
    return lesson


def _started(store, step):
    return bool(step.get('turn_id')) and store.get('streams', step['turn_id']) is not None


def begin(store, request):
    """A new stepped lesson for a section with its initial plan (titles, in order)."""
    identifier = require_text(request, 'id')
    concept = require_text(request, 'concept_id')
    validate_concept(store, concept)
    old = store.get('lessons', identifier)
    if old:
        if old['concept_id'] != concept:
            raise OperationError('id_conflict', identifier)
        return {'lesson': old, 'created': False}
    titles = request.get('steps')
    if not isinstance(titles, list) or not 1 <= len(titles) <= MAX_STEPS:
        raise OperationError('invalid_plan', f'A lesson plan has 1 to {MAX_STEPS} steps')
    focus = request.get('request', '')
    if not isinstance(focus, str):
        raise OperationError('invalid_request', 'request must be a string')
    lesson = {'id': identifier, 'concept_id': concept, 'request': focus.strip(), 'created_at': time.time(),
              'steps': [{'title': _title(t), 'added': False} for t in titles]}
    return {'lesson': store.put('lessons', identifier, lesson), 'created': True}


def step(store, request):
    """Assign the next planned step to a turn. The previous step must be complete; a step whose turn never started
    (the host stopped in between) is free again."""
    lesson = _read(store, require_text(request, 'id'))
    turn_id = require_text(request, 'turn_id')
    for index, item in enumerate(lesson['steps']):
        if item.get('turn_id') == turn_id:
            return {'lesson': lesson, 'number': index + 1, 'created': False}
    for item in lesson['steps']:
        if item.get('turn_id') and not _started(store, item):
            item.pop('turn_id')
    taught = [item for item in lesson['steps'] if item.get('turn_id')]
    if taught and store.get('streams', taught[-1]['turn_id'])['status'] != 'completed':
        raise OperationError('step_unfinished', 'Finish the current step first')
    if len(taught) == len(lesson['steps']):
        raise OperationError('lesson_finished', 'This lesson has no steps left')
    lesson['steps'][len(taught)]['turn_id'] = turn_id
    store.put('lessons', lesson['id'], lesson)
    return {'lesson': lesson, 'number': len(taught) + 1, 'created': True}


def reply(store, request):
    """Record a completed step's structured reply: optionally the title of what it taught and the revised plan of the
    steps still to teach (`remaining`, each {title, added}). Recorded once per step."""
    lesson = _read(store, require_text(request, 'id'))
    turn_id = require_text(request, 'turn_id')
    index = next((i for i, item in enumerate(lesson['steps']) if item.get('turn_id') == turn_id), None)
    if index is None:
        raise OperationError('unknown_step', turn_id)
    turn = store.get('streams', turn_id)
    if not turn or turn['status'] != 'completed':
        raise OperationError('step_unfinished', 'Only a completed step has a reply')
    entry = lesson['steps'][index]
    if entry.get('replied'):
        return {'lesson': lesson, 'changed': False}
    title = _title(request['title']) if 'title' in request else None
    revised = None
    # A later step already started keeps the plan as it was taught.
    if 'remaining' in request and not any(item.get('turn_id') for item in lesson['steps'][index + 1:]):
        remaining = request['remaining']
        if not isinstance(remaining, list) or index + 1 + len(remaining) > MAX_STEPS:
            raise OperationError('invalid_plan', f'A lesson plan has at most {MAX_STEPS} steps')
        added = {item['title'] for item in lesson['steps'] if item.get('added')}
        revised = []
        for item in remaining:
            if not isinstance(item, dict) or not isinstance(item.get('added', False), bool):
                raise OperationError('invalid_plan', 'Each remaining step is {title, added}')
            text = _title(item.get('title'))
            if text in {r['title'] for r in revised}:
                raise OperationError('invalid_plan', 'Remaining steps repeat a title')
            revised.append({'title': text, 'added': item.get('added', False) or text in added})
    if title:
        entry['title'] = title
    if revised is not None:
        lesson['steps'] = lesson['steps'][:index + 1] + revised
    entry['replied'] = True
    store.put('lessons', lesson['id'], lesson)
    return {'lesson': lesson, 'changed': True}


def read(store, request):
    return {'lesson': _read(store, require_text(request, 'id'))}


def list_lessons(store, request):
    lessons = sorted(store.list('lessons'), key=lambda item: item['created_at'])
    if request.get('concept_id'):
        lessons = [item for item in lessons if item['concept_id'] == request['concept_id']]
    return {'lessons': lessons}


OPERATIONS = {'lesson.begin': begin, 'lesson.step': step, 'lesson.reply': reply, 'lesson.read': read, 'lesson.list': list_lessons}
