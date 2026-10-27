"""Stepped lessons (ADR 0009): a section's lesson is taught as lesson steps, one mainline turn each, following a plan
the teacher may revise as it teaches. Each step may end with a check question, answered without a model turn and
recorded as an interaction, never as evidence. Lessons saved before this module are single turns with no record here."""
import random
import time
from .memory import from_check
from .streaming import PREPARED_STEP, reveal
from .store import OperationError
from .teaching import record_interaction, require_text, validate_concept

MAX_STEPS = 8  # a sanity cap on the whole plan, bridges included; the teacher decides the count
MAX_TITLE = 200
MAX_OPTIONS = 5  # besides "I'm not sure", which the interface adds
MAX_CHECK_TEXT = 1000
UNSURE = 'unsure'


def _title(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_TITLE:
        raise OperationError('invalid_plan', f'A step title must be text of at most {MAX_TITLE} characters')
    return value.strip()


def _check_text(value, limit=MAX_CHECK_TEXT):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise OperationError('invalid_check', f'Check question text must be nonempty and at most {limit} characters')
    return value.strip()


def _check(value, seed):
    """A check question {idea, question, options: [{text, explanation}], correct}. Options are shuffled once, so the
    correct one does not always come first."""
    if not isinstance(value, dict):
        raise OperationError('invalid_check', 'A check question is {idea, question, options, correct}')
    options = value.get('options')
    correct = value.get('correct')
    if not isinstance(options, list) or not 2 <= len(options) <= MAX_OPTIONS:
        raise OperationError('invalid_check', f'A check question has 2 to {MAX_OPTIONS} options')
    if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct < len(options):
        raise OperationError('invalid_check', 'correct must be the index of an option')
    cleaned = []
    for option in options:
        if not isinstance(option, dict):
            raise OperationError('invalid_check', 'Each option is {text, explanation}')
        cleaned.append({'text': _check_text(option.get('text'), MAX_TITLE * 2), 'explanation': _check_text(option.get('explanation'))})
    if len({o['text'] for o in cleaned}) < len(cleaned):
        raise OperationError('invalid_check', 'Options repeat a text')
    order = list(range(len(cleaned)))
    random.Random(seed).shuffle(order)
    return {'idea': _check_text(value.get('idea'), MAX_TITLE), 'question': _check_text(value.get('question')),
            'options': [cleaned[i] for i in order], 'correct': order.index(correct)}


def _read(store, identifier):
    lesson = store.get('lessons', identifier)
    if lesson is None:
        raise OperationError('unknown_lesson', identifier)
    return lesson


def _step_of(store, request):
    """The lesson, turn id and index of the step a request names by lesson `id` and `turn_id`."""
    lesson = _read(store, require_text(request, 'id'))
    turn_id = require_text(request, 'turn_id')
    index = next((i for i, item in enumerate(lesson['steps']) if item.get('turn_id') == turn_id), None)
    if index is None:
        raise OperationError('unknown_step', turn_id)
    return lesson, turn_id, index


def _started(store, step):
    return bool(step.get('turn_id')) and store.get('streams', step['turn_id']) is not None


def begin(store, request):
    """A new stepped lesson for a section with its initial plan (titles, in order) and an optional `outline`: the steps to
    fall back on when the first step's reply plans none."""
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
    outline = request.get('outline') or []
    if not isinstance(outline, list) or len(outline) > MAX_STEPS:
        raise OperationError('invalid_plan', f'A lesson outline has at most {MAX_STEPS} steps')
    lesson = {'id': identifier, 'concept_id': concept, 'request': focus.strip(), 'created_at': time.time(),
              'steps': [{'title': _title(t), 'added': False} for t in titles],
              **({'outline': [_title(t) for t in outline]} if outline else {})}
    return {'lesson': store.put('lessons', identifier, lesson), 'created': True}


def step(store, request):
    """Assign the next planned step to a turn. The previous step must be complete; a step whose turn never started
    (the host stopped in between) is free again. The lesson's prepared step (lesson.prepare) is revealed as the mainline
    turn it was written as; any other assignment drops it. An optional `request_id` makes the request idempotent."""
    lesson = _read(store, require_text(request, 'id'))
    turn_id = require_text(request, 'turn_id')
    request_id = request.get('request_id')
    for index, item in enumerate(lesson['steps']):
        if item.get('turn_id') == turn_id or (request_id and item.get('request_id') == request_id):
            return {'lesson': lesson, 'number': index + 1, 'created': False}
    for item in lesson['steps']:
        if item.get('turn_id') and not _started(store, item):
            item.pop('turn_id')
    taught = [item for item in lesson['steps'] if item.get('turn_id')]
    if taught and store.get('streams', taught[-1]['turn_id'])['status'] != 'completed':
        raise OperationError('step_unfinished', 'Finish the current step first')
    if len(taught) == len(lesson['steps']):
        raise OperationError('lesson_finished', 'This lesson has no steps left')
    turn = store.get('streams', turn_id)
    if lesson.pop('prepared', None) == turn_id:
        reveal(store, turn)
    elif turn and turn['channel'] == PREPARED_STEP:
        raise OperationError('not_prepared', 'This turn is not the prepared step of the lesson')
    entry = lesson['steps'][len(taught)]
    entry['turn_id'] = turn_id
    if isinstance(request_id, str) and request_id:
        entry['request_id'] = request_id
    store.put('lessons', lesson['id'], lesson)
    return {'lesson': lesson, 'number': len(taught) + 1, 'created': True}


def prepare(store, request):
    """Record the lesson's prepared step: a turn writing its next step ahead, on the prepared_step channel, whose prompt
    snapshot names the lesson and step number; `turn_id` null drops it. A lesson has at most one; the host stops the
    one replaced."""
    lesson = _read(store, require_text(request, 'id'))
    turn_id = request.get('turn_id')
    previous = lesson.get('prepared')
    if turn_id is None:
        lesson.pop('prepared', None)
    else:
        turn = store.get('streams', require_text(request, 'turn_id'))
        ahead = (turn or {}).get('prompt_snapshot', {}).get('lesson_step') or {}
        if not turn or turn['channel'] != PREPARED_STEP or ahead.get('lesson_id') != lesson['id']:
            raise OperationError('not_prepared', 'Prepare a step with a prepared_step turn of this lesson')
        if ahead.get('number') != sum(1 for item in lesson['steps'] if item.get('turn_id')) + 1:
            raise OperationError('not_prepared', 'A prepared step is the next step of the lesson')
        lesson['prepared'] = turn_id
    store.put('lessons', lesson['id'], lesson)
    return {'lesson': lesson, 'previous': previous}


def reply(store, request):
    """Record a completed step's structured reply: optionally the title of what it taught, the revised plan of the
    steps still to teach (`remaining`, each {title, added}) and its check question (`check`). Recorded once per step."""
    lesson, turn_id, index = _step_of(store, request)
    turn = store.get('streams', turn_id)
    if not turn or turn['status'] != 'completed':
        raise OperationError('step_unfinished', 'Only a completed step has a reply')
    entry = lesson['steps'][index]
    if entry.get('replied'):
        return {'lesson': lesson, 'changed': False}
    title = _title(request['title']) if 'title' in request else None
    check = _check(request['check'], turn_id) if 'check' in request else None
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
    if revised is None and index == 0 and lesson.get('outline') and len(lesson['steps']) == 1:
        # The teacher plans in its first reply; one that plans nothing keeps to the section overview's steps after this one.
        revised = [{'title': t, 'added': False} for t in lesson['outline'][1:]]
        title = title or lesson['outline'][0]
    if title:
        entry['title'] = title
    if revised is not None:
        lesson['steps'] = lesson['steps'][:index + 1] + revised
    if check:
        entry['check'] = check
    entry['replied'] = True
    store.put('lessons', lesson['id'], lesson)
    return {'lesson': lesson, 'changed': True}


def answer(store, request):
    """The learner's choice on a step's check question: an option's index or "unsure". Recorded once, as an interaction
    and never as evidence, while the next step has not started; continuing without answering leaves it unanswered.
    Repeated misses on the check's idea become a difficulty in course memory, and a correct answer clears it."""
    lesson, turn_id, index = _step_of(store, request)
    entry = lesson['steps'][index]
    check = entry.get('check')
    if not check:
        raise OperationError('no_check', 'This step has no check question')
    choice = request.get('choice')
    if choice != UNSURE and (not isinstance(choice, int) or isinstance(choice, bool) or not 0 <= choice < len(check['options'])):
        raise OperationError('invalid_choice', 'Choose an option or "unsure"')
    if entry.get('answer'):
        if entry['answer']['choice'] != choice:
            raise OperationError('already_answered', 'This check question is already answered')
        return {'lesson': lesson, 'answer': entry['answer'], 'changed': False}
    if any(_started(store, item) for item in lesson['steps'][index + 1:]):
        raise OperationError('check_closed', 'The next step has started')
    chosen = "I'm not sure" if choice == UNSURE else check['options'][choice]['text']
    interaction = record_interaction(store, {'id': 'check-answer:' + turn_id, 'role': 'user', 'kind': 'check_answer', 'concept_id': lesson['concept_id'],
                                             'text': f"Check question: {check['question']}\nAnswer: {chosen}", 'source_refs': []})['interaction']
    entry['answer'] = {'choice': choice, 'unsure': choice == UNSURE, 'correct': choice == check['correct'],
                       'interaction_id': interaction['id'], 'answered_at': time.time()}
    store.put('lessons', lesson['id'], lesson)
    from_check(store, lesson['concept_id'], check['idea'])
    return {'lesson': lesson, 'answer': entry['answer'], 'changed': True}


def read(store, request):
    return {'lesson': _read(store, require_text(request, 'id'))}


def list_lessons(store, request):
    lessons = sorted(store.list('lessons'), key=lambda item: item['created_at'])
    if request.get('concept_id'):
        lessons = [item for item in lessons if item['concept_id'] == request['concept_id']]
    return {'lessons': lessons}


OPERATIONS = {'lesson.begin': begin, 'lesson.step': step, 'lesson.prepare': prepare, 'lesson.reply': reply, 'lesson.answer': answer, 'lesson.read': read, 'lesson.list': list_lessons}
