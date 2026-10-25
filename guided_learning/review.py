"""Spaced review schedule (ADR 0008), computed from assessment evidence whenever it is read.

A section becomes reviewable once one of its exercises is assessed `passed`. Its review is due INTERVALS[step] days
after the last pass. A review (a task with origin `review`, or a `recap` task, which reviews every section it tests)
moves the step: an unaided pass to the next interval, an assisted pass keeps it, `needs_work` returns to the first. An
ordinary exercise passed later restarts the wait at the same step. Sections skipped with their chapter are not scheduled.
"""
import time
from datetime import datetime

from .store import OperationError

DAY = 86400
INTERVALS = (1, 3, 7, 21, 60)
DAILY_CAP = 5
REVIEW_ORIGINS = ('review', 'recap')
UNAIDED = ('independent', 'retest_passed')


def _now(request):
    now = request.get('now', time.time())
    if not isinstance(now, (int, float)) or isinstance(now, bool):
        raise OperationError('invalid_request', 'now must be a number of seconds')
    return float(now)


def start_of_day(now):
    """Local midnight before `now`; the daily cap counts reviews since then."""
    return datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def assessments(store):
    """Each assessment in the order it was made, with the sections it reviews and whether it was a review."""
    tasks = {t['id']: t for t in store.list('practice_tasks')}
    events = []
    for item in store.list('evidence'):
        if 'assessment_id' not in item:
            continue
        interaction = store.get('interactions', item['assessment_id']) or {}
        task = tasks.get(item.get('exercise_id')) or {}
        origin = task.get('origin')
        sections = task.get('tests_concept_ids') if origin == 'recap' and task.get('tests_concept_ids') else [item['concept_id']]
        events.append({'sequence': interaction.get('sequence', 0), 'at': item.get('assessed_at') or 0, 'kind': item['kind'],
                       'passed': item['outcome'] == 'passed', 'review': origin in REVIEW_ORIGINS, 'sections': sections})
    return sorted(events, key=lambda e: e['sequence'])


def section_states(events):
    """Fold assessments into each section's interval step, the time its wait started and its last review."""
    states = {}
    for event in events:
        for cid in event['sections']:
            state = states.get(cid)
            if state is None:
                if event['passed']:
                    states[cid] = {'step': 0, 'anchor': event['at'], 'last_review': None}
                continue
            if event['review']:
                if not event['passed']:
                    state['step'] = 0
                elif event['kind'] in UNAIDED:
                    state['step'] = min(state['step'] + 1, len(INTERVALS) - 1)
                state['anchor'] = event['at']
                state['last_review'] = event['at']
            elif event['passed']:
                state['anchor'] = event['at']
    return states


def skipped(store):
    resolved = {r['deferred_id'] for r in store.list('evidence_resolutions')}
    return {d['concept_id'] for d in store.list('evidence_deferred') if d['id'].startswith('chapter-skip:') and d['id'] not in resolved}


def open_reviews(store):
    """Review questions generated but not yet answered, by section."""
    return {t['concept_id']: t['id'] for t in store.list('practice_tasks')
            if t.get('origin') == 'review' and t.get('status') != 'deferred' and not any(h.get('action') == 'assess' for h in t.get('history', []))}


def schedule(store, request):
    now = _now(request)
    model = store.get('curriculum', 'model', {})
    route = set(model.get('route', []))
    states = section_states(assessments(store))
    excluded = skipped(store)
    postponed = {p['concept_id']: p['at'] for p in store.list('review_postponements')}
    started = open_reviews(store)
    today = start_of_day(now)
    sections = []
    for cid, state in states.items():
        if cid not in route or cid in excluded:
            continue
        due = state['anchor'] + INTERVALS[state['step']] * DAY
        if postponed.get(cid, -1) >= state['anchor']:
            due = max(due, postponed[cid] + DAY)
        sections.append({'concept_id': cid, 'step': state['step'], 'interval_days': INTERVALS[state['step']], 'due_at': due,
                         'last_review_at': state['last_review'], 'task_id': started.get(cid)})
    done_today = sorted({s['concept_id'] for s in sections if s['last_review_at'] is not None and today <= s['last_review_at'] <= now})
    # A review already started stays listed until it is answered; the rest fill what is left of today's cap.
    in_progress = sorted((s for s in sections if s['task_id']), key=lambda s: s['due_at'])
    waiting = sorted((s for s in sections if not s['task_id'] and s['due_at'] <= now), key=lambda s: s['due_at'])
    room = max(0, DAILY_CAP - len(done_today) - len(in_progress))
    upcoming = [s for s in sections if not s['task_id'] and s['due_at'] > now]
    return {'due': in_progress + waiting[:room], 'waiting': len(waiting) - min(room, len(waiting)), 'upcoming': len(upcoming),
            'next_due_at': min((s['due_at'] for s in upcoming), default=None), 'reviewable': len(sections),
            'done_today': len(done_today), 'cap': DAILY_CAP, 'now': now,
            'sections': sorted(sections, key=lambda s: s['due_at'])}


def postpone(store, request):
    """"Not now": the section's review waits one more day from now."""
    cid = request.get('concept_id')
    now = _now(request)
    current = next((s for s in schedule(store, {'now': now})['sections'] if s['concept_id'] == cid), None)
    if current is None:
        raise OperationError('not_reviewable', 'This section has no review scheduled')
    if current['due_at'] > now:
        raise OperationError('not_due', 'This section is not due for review yet')
    store.put('review_postponements', cid, {'concept_id': cid, 'at': now})
    return {'postponed': {'concept_id': cid, 'until': now + DAY}}


OPERATIONS = {'review.schedule': schedule, 'review.postpone': postpone}
