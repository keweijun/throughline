"""The mistakes book (issue #219): the learner's misses, read from what the course already records, never stored. It
holds every missed exercise part (a section's exercise, a chapter quiz question or a written review answer), every
wrong recall answer, and an idea whose check questions were missed more than once, the point at which a miss stops
being a slip (ADR 0010). An entry the learner later gets right stays, marked with when: there is nothing to clear."""
from .memory import idea_key
from .review import MISSES

REPEATED_CHECKS = 2  # check misses on one idea before it is a mistake rather than a slip, as for a difficulty


def _part_text(part):
    if isinstance(part, dict):
        return ' '.join(str(part[k]) for k in ('label', 'text') if part.get(k))
    return str(part)


def _kind(task):
    return {'review': 'review', 'chapter_quiz': 'quiz'}.get(task.get('origin'), 'exercise')


def _tested(task):
    return task.get('tests_concept_ids') or [task['concept_id']]


def _base(task):
    return {'kind': _kind(task), 'concept_id': _tested(task)[0], 'concept_ids': _tested(task), 'task_id': task['id'],
            'question': task['question'], **({'chapter_id': task['chapter_id']} if task.get('chapter_id') else {})}


def _parts(task, assessed_at):
    """One entry per part missed in an assessment: the answer and feedback of its latest miss, and when a later
    assessment found that part correct. Part statuses are kept whole from one assessment to the next."""
    found = []
    assessments = [(h, assessed_at.get(h.get('evidence_id'))) for h in task.get('history', []) if h.get('action') == 'assess']
    width = max((len(h.get('parts') or []) for h, _ in assessments), default=0)
    parts = task.get('parts') or []
    for index in range(width):
        statuses = [((h.get('parts') or [])[index] if index < len(h.get('parts') or []) else None, h, at) for h, at in assessments]
        missed = [i for i, (status, _, _) in enumerate(statuses) if status in MISSES]
        if not missed:
            continue
        last = missed[-1]
        right = next((at for status, _, at in statuses[last + 1:] if status == 'correct'), None)
        _, entry, at = statuses[last]
        found.append({**_base(task), 'id': f'part:{task["id"]}:{index}',
                      **({'part': _part_text(parts[index])} if len(parts) > 1 and index < len(parts) else {}),
                      'answer': entry.get('answer', ''), 'feedback': entry.get('feedback', ''),
                      'missed_at': statuses[missed[0]][2] or at, 'last_missed_at': at, 'right_at': right})
    return found


def _ideas(store, tasks):
    """Every answer on an idea, recall or check, as (time, correct, where): what marks a miss on it as since got right."""
    answers = {}
    for task in tasks:
        if task.get('answer') and task.get('idea'):
            answers.setdefault(idea_key(task['idea']), []).append((task['answer'].get('at') or 0, task['answer']['correct'], task))
    for lesson in store.list('lessons'):
        for step in lesson['steps']:
            if step.get('check') and step.get('answer'):
                answers.setdefault(idea_key(step['check']['idea']), []).append((step['answer']['answered_at'], step['answer']['correct'], (lesson, step)))
    return {key: sorted(found, key=lambda a: a[0]) for key, found in answers.items()}


def _right_after(answers, at):
    return next((when for when, correct, _ in answers if correct and when > at), None)


def entries(store, _request=None):
    """The mistakes book, open entries first (newest miss first), then those since got right (most recent first)."""
    tasks = [t for t in store.list('practice_tasks') if t.get('status') not in ('replaced', 'retired')]
    assessed_at = {e['id']: e.get('assessed_at') for e in store.list('evidence')}
    ideas = _ideas(store, tasks)
    found = []
    for task in tasks:
        found += _parts(task, assessed_at)
        answer = task.get('answer')
        if answer and not answer['correct']:
            chosen = None if answer['choice'] == 'unsure' else task['options'][answer['choice']]
            right = task['options'][task['correct']]
            at = answer.get('at') or 0
            found.append({**_base(task), 'id': f'recall:{task["id"]}', 'idea': task.get('idea', ''),
                          'chosen': chosen['text'] if chosen else None, 'why': (chosen or right)['explanation'],
                          'correct_answer': right['text'], 'missed_at': at, 'last_missed_at': at,
                          'right_at': _right_after(ideas.get(idea_key(task.get('idea', '')), []), at)})
    for key, answers in ideas.items():
        missed = [a for a in answers if not a[1] and isinstance(a[2], tuple)]
        if len(missed) < REPEATED_CHECKS:
            continue
        at, _, (lesson, step) = missed[-1]
        check, answer = step['check'], step['answer']
        chosen = None if answer['unsure'] else check['options'][answer['choice']]
        right = check['options'][check['correct']]
        found.append({'id': 'check:' + key, 'kind': 'check', 'concept_id': lesson['concept_id'], 'concept_ids': [lesson['concept_id']],
                      'turn_id': step['turn_id'], 'idea': check['idea'], 'question': check['question'],
                      'chosen': chosen['text'] if chosen else None, 'why': (chosen or right)['explanation'], 'correct_answer': right['text'],
                      'missed_at': missed[0][0], 'last_missed_at': at, 'right_at': _right_after(answers, at)})
    open_, right = [e for e in found if not e['right_at']], [e for e in found if e['right_at']]
    return {'entries': sorted(open_, key=lambda e: -(e['last_missed_at'] or 0)) + sorted(right, key=lambda e: -e['right_at'])}


OPERATIONS = {'mistakes.list': entries}
