"""Review on request (ADR 0014): review sets, the review context the teacher chooses questions from, recall answers and
warm-ups. Nothing is scheduled: how long ago each studied section was practised is context, computed when read."""
import time

from . import curriculum, streaming
from .lessons import UNSURE
from .store import OperationError
from .teaching import record_interaction, require_text

DAY = 86400
KINDS = ('for_me', 'request', 'warm_up', 'chapter_quiz')
MAX_QUESTIONS = 8  # a sanity cap on one set; the teacher decides how many it needs
MAX_REQUEST = 1000
MAX_NOTE = 600
WARM_UP_AFTER = 7 * DAY  # a prerequisite practised longer ago than this is offered as a warm-up
MISSES = ('partly_correct', 'not_yet')
RECENT_MISSES = 3
EARLIER_QUESTIONS = 20

# A section is skipped by skipping the rest of its chapter or by jumping past it to a later section (ADR 0006).
SKIP_PREFIXES = ('chapter-skip:', 'route-skip:')


def skipped(store):
    resolved = {r['deferred_id'] for r in store.list('evidence_resolutions')}
    return {d['concept_id'] for d in store.list('evidence_deferred') if d['id'].startswith(SKIP_PREFIXES) and d['id'] not in resolved}


def studied_sections(store):
    """Sections with a completed lesson of their own (a chapter recap is not one) or any learning evidence, such as
    sections taught in Codex chat before the app."""
    return ({t['concept_id'] for t in store.digest('streams', streaming.brief) if t['channel'] == 'mainline' and t['status'] == 'completed' and not t.get('chapter_id')}
            | {e['concept_id'] for e in store.list('evidence')})


def reviewable(store):
    """Studied sections still on the route and not skipped, in route order: what a review may test."""
    studied = studied_sections(store) - skipped(store)
    return [cid for cid in curriculum.model(store)['route'] if cid in studied]


def _tested(task):
    return task.get('tests_concept_ids') or [task['concept_id']]


def _assessments(task):
    return [h for h in task.get('history', []) if h.get('action') == 'assess']


def answered(task):
    """A review question is answered once its recall choice is made or its written answer has been assessed."""
    return bool(task.get('answer') or _assessments(task))


def outcome(task):
    """How a review or quiz question went: right, missed, partly (some parts still open) or unanswered."""
    if task.get('answer'):
        return 'right' if task['answer']['correct'] else 'missed'
    last = next(iter(reversed(_assessments(task))), None)
    if not last:
        return 'unanswered'
    if last.get('outcome') == 'passed':
        return 'right'
    return 'missed' if any(p in MISSES for p in last.get('parts') or ['not_yet']) else 'partly'


def last_practised(store):
    """When each section was last practised: its latest lesson, assessment or review answer."""
    times = {}

    def seen(cid, at):
        if at and at > times.get(cid, 0):
            times[cid] = at
    for turn in store.digest('streams', streaming.brief):
        if turn['channel'] == 'mainline' and turn['status'] == 'completed' and not turn.get('chapter_id'):
            seen(turn['concept_id'], turn.get('started_at'))
    for item in store.list('evidence'):
        if 'assessment_id' in item:
            seen(item['concept_id'], item.get('assessed_at'))
    for task in store.list('practice_tasks'):
        if task.get('answer'):
            for cid in _tested(task):
                seen(cid, task['answer'].get('at'))
    return times


def scope_sections(store, value):
    """The sections a set may test: reviewable ones, narrowed by its scope or, for a warm-up, to the section's prerequisites."""
    allowed = reviewable(store)
    if value.get('kind') == 'warm_up':
        concept = next((c for c in curriculum.model(store)['concepts'] if c['id'] == value.get('concept_id')), None)
        wanted = set(concept.get('prerequisites', [])) if concept else set()
        return [c for c in allowed if c in wanted]
    scope = value.get('scope') or {}
    if not scope:
        return allowed
    chapters = {c['id']: c['concept_ids'] for c in curriculum.view(store, {})['chapters']}
    wanted = set(scope.get('concept_ids', [])) | {cid for ch in scope.get('chapter_ids', []) for cid in chapters.get(ch, [])}
    return [c for c in allowed if c in wanted]


def context(store, request):
    """The review context (ADR 0014): what the teacher chooses questions from, for the sections in a set's scope."""
    now = request.get('now', time.time())
    sections = request.get('sections')
    if request.get('set_id'):
        sections = scope_sections(store, store.get('review_sets', request['set_id']) or {})
    if sections is None:
        sections = reviewable(store)
    model = curriculum.model(store)
    concepts = {c['id']: c for c in model['concepts']}
    practised = last_practised(store)
    tasks = sorted(store.list('practice_tasks'), key=lambda t: t.get('created_at', 0))
    lessons = {lesson['concept_id']: lesson for lesson in sorted(store.list('lessons'), key=lambda x: x.get('created_at', 0))}
    result = []
    for cid in sections:
        concept = concepts.get(cid, {})
        mine = [t for t in tasks if cid in _tested(t) and t.get('status') != 'replaced']
        misses = [t['question'] for t in mine if outcome(t) in ('missed', 'partly')][-RECENT_MISSES:]
        entry = {'id': cid, 'title': concept.get('title', cid),
                 **{k: concept[k] for k in ('core_question', 'objective') if concept.get(k)},
                 'days_since_practised': int((now - practised[cid]) // DAY) if cid in practised else None,
                 'recent_misses': misses,
                 'set_aside': [t['question'] for t in mine if t.get('status') == 'deferred']}
        if cid in lessons:
            entry['lesson_steps'] = [s['title'] for s in lessons[cid]['steps']]
        result.append(entry)
    earlier = [{'question': t['question'], 'sections': _tested(t), 'outcome': outcome(t)}
               for t in tasks if t.get('origin') in ('review', 'chapter_quiz')][-EARLIER_QUESTIONS:]
    return {'sections': result, 'earlier': earlier}


def _text(value, limit, name):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise OperationError('invalid_request', f'{name} must be text of at most {limit} characters')
    return value.strip() or None


def create(store, request):
    """A review set asked for now (ADR 0014). Its questions are written by a practice job with purpose review."""
    identifier = require_text(request, 'id')
    previous = store.get('review_sets', identifier)
    if previous:
        return {'set': previous, 'sections': scope_sections(store, previous)}
    kind = request.get('kind')
    if kind not in KINDS or kind == 'chapter_quiz':
        raise OperationError('invalid_request', 'kind must be for_me, request or warm_up')
    value = {'id': identifier, 'kind': kind, 'created_at': time.time()}
    text = _text(request.get('request'), MAX_REQUEST, 'request')
    if kind == 'request' and not text and not request.get('scope'):
        raise OperationError('empty_request', 'Say what to review or choose chapters')
    if text:
        value['request'] = text
    scope = request.get('scope')
    if scope:
        if not isinstance(scope, dict) or set(scope) - {'chapter_ids', 'concept_ids'} or not all(
                isinstance(scope.get(k, []), list) and all(isinstance(i, str) for i in scope.get(k, [])) for k in ('chapter_ids', 'concept_ids')):
            raise OperationError('invalid_request', 'scope lists chapter_ids and concept_ids')
        value['scope'] = {k: list(dict.fromkeys(scope[k])) for k in ('chapter_ids', 'concept_ids') if scope.get(k)}
    if kind == 'warm_up':
        value['concept_id'] = require_text(request, 'concept_id')
    if request.get('prepared'):
        value['prepared'] = True
    sections = scope_sections(store, value)
    if not sections:
        raise OperationError('nothing_to_review', 'Nothing studied matches this review yet')
    return {'set': store.put('review_sets', identifier, value), 'sections': sections}


def chapter_quiz_set(store, quiz_id, chapter_id, created_at=None):
    """A chapter quiz is a review set scoped to its chapter (ADR 0014); its id is the quiz's."""
    return store.get('review_sets', quiz_id) or store.put('review_sets', quiz_id, {
        'id': quiz_id, 'kind': 'chapter_quiz', 'chapter_id': chapter_id, 'scope': {'chapter_ids': [chapter_id]},
        'created_at': created_at or time.time()})


def take_prepared(store, request):
    """Review for me uses the prepared set: it becomes an ordinary set, dated now."""
    value = store.get('review_sets', require_text(request, 'id'))
    if not value or not value.get('prepared'):
        raise OperationError('unknown_review_set', 'No prepared review set')
    value.pop('prepared')
    value['created_at'] = time.time()
    return {'set': store.put('review_sets', value['id'], value)}


def sets(store, request):
    """Every set with its questions' outcomes, newest first; a prepared set stays hidden until asked for."""
    tasks = [t for t in store.list('practice_tasks') if t.get('set_id')]
    listed = []
    for value in sorted(store.list('review_sets'), key=lambda s: -s.get('created_at', 0)):
        mine = [t for t in tasks if t['set_id'] == value['id']]
        outcomes = [outcome(t) for t in mine]
        listed.append({**value, 'task_ids': [t['id'] for t in sorted(mine, key=lambda t: t['id'])],
                       'answered': sum(o != 'unanswered' for o in outcomes), 'right': outcomes.count('right'),
                       'open': bool(mine) and not value.get('closed_at') and 'unanswered' in outcomes})
    return {'sets': listed}


def close(store, request):
    value = store.get('review_sets', require_text(request, 'id'))
    if not value:
        raise OperationError('unknown_review_set', 'Unknown review set')
    if not value.get('closed_at'):
        value['closed_at'] = time.time()
        store.put('review_sets', value['id'], value)
    return {'set': value}


def answer(store, request):
    """A recall question's choice (ADR 0014): feedback comes from the explanations it was written with. It is recorded
    once, as an interaction, and is never learning evidence."""
    task = store.get('practice_tasks', require_text(request, 'task_id'))
    if not task or task.get('kind') != 'recall':
        raise OperationError('unknown_exercise', 'Only a recall question is answered by choosing')
    if task.get('answer'):
        return {'task': task}
    choice = request.get('choice')
    if choice != UNSURE and (not isinstance(choice, int) or isinstance(choice, bool) or not 0 <= choice < len(task['options'])):
        raise OperationError('invalid_request', 'choice is an option index or unsure')
    iid = 'review-answer:' + task['id']
    text = task['options'][choice]['text'] if isinstance(choice, int) else "I'm not sure"
    record_interaction(store, {'id': iid, 'role': 'user', 'kind': 'review_answer', 'concept_id': task['concept_id'], 'text': text})
    task['answer'] = {'choice': choice, 'correct': choice == task['correct'], 'interaction_id': iid, 'at': time.time()}
    task['status'] = 'attempted'
    return {'task': store.put('practice_tasks', task['id'], task)}


def warm_ups(store, request):
    """Sections whose lesson has not started and that build on a studied prerequisite not practised for a while, with
    those prerequisites; offered once each (ADR 0014). `reviewable` counts the sections a review may test."""
    now = request.get('now', time.time())
    model = curriculum.model(store)
    allowed = set(reviewable(store))
    practised = last_practised(store)
    started = {t['concept_id'] for t in store.digest('streams', streaming.brief) if t['channel'] == 'mainline' and not t.get('chapter_id')}
    done = {w['concept_id'] for w in store.list('review_warm_ups')} | {s['concept_id'] for s in store.list('review_sets') if s.get('kind') == 'warm_up'}
    offers = {}
    for concept in model['concepts']:
        cid = concept['id']
        if cid in started or cid in done or cid not in model['route']:
            continue
        stale = [p for p in concept.get('prerequisites', []) if p in allowed and now - practised.get(p, 0) >= WARM_UP_AFTER]
        if stale:
            offers[cid] = stale
    return {'warm_ups': offers, 'reviewable': len(allowed)}


def dismiss_warm_up(store, request):
    cid = require_text(request, 'concept_id')
    store.put('review_warm_ups', cid, {'concept_id': cid, 'dismissed_at': time.time()})
    return {'dismissed': cid}


OPERATIONS = {'review.context': context, 'review.create': create, 'review.take_prepared': take_prepared, 'review.sets': sets,
              'review.close': close, 'review.answer': answer, 'review.warm_ups': warm_ups, 'review.dismiss_warm_up': dismiss_warm_up}
