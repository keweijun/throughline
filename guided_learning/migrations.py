"""Forward-only course migrations (ADR 0007).

A course records its format version in `course/schema`; courses without it are version 1. `upgrade` runs inside the
first operation's transaction, so a migration commits or rolls back with it. MIGRATIONS[i] moves a course from
version i + 1 to i + 2. Each migration must be idempotent and keep learning evidence and raw interactions intact.
"""
from datetime import datetime

from .store import OperationError


def lecture_excerpt(turn):
    """What a side question keeps of the lesson its passage came from: the text and its sources, not the lesson's own prompt."""
    concept = ((turn.get('prompt_snapshot') or {}).get('context') or {}).get('concept') or {}
    return {'id': turn['id'], 'concept_id': turn.get('concept_id') or concept.get('id'), 'title': turn.get('title') or concept.get('title'),
            'status': turn.get('status'), 'text': turn.get('final_text') or turn.get('text') or '', 'source_refs': turn.get('source_refs', [])}


def slim_selected_lectures(store):
    """Side questions stored the whole selected lesson record, prompt snapshot included, and copied it into every answer's snapshot."""
    def slim(branch):
        selected = branch.get('selected_lecture')
        if isinstance(selected, dict) and 'prompt_snapshot' in selected:
            branch['selected_lecture'] = lecture_excerpt(selected)
            return True
        return False
    for branch in store.list('web_branches'):
        if slim(branch):
            store.put('web_branches', branch['id'], branch)
    for turn in store.list('streams'):
        branch = (turn.get('prompt_snapshot') or {}).get('branch')
        if isinstance(branch, dict) and slim(branch):
            store.put('streams', turn['id'], turn)


def group_flat_routes(store):
    """Courses built before chapters become one chapter, so every course is taught the same way (ADR 0006)."""
    from .curriculum import whole_course_chapter
    model = store.get('curriculum', 'model')
    if isinstance(model, dict) and model.get('route') and not model.get('chapters'):
        model['chapters'] = [whole_course_chapter(store, model['route'])]
        store.put('curriculum', 'model', model)


def date_assessments(store):
    """The review schedule reads when each assessment was made (ADR 0008). An assessment made in the app is dated by the
    practice turn that produced it; one recorded elsewhere has no such turn and stays undated, which reads as long ago."""
    for item in store.list('evidence'):
        if 'assessment_id' not in item or 'assessed_at' in item or not item['id'].startswith('practice-evidence:'):
            continue
        turn = store.get('streams', item['id'].removeprefix('practice-evidence:'))
        if turn and isinstance(turn.get('started_at'), (int, float)):
            item['assessed_at'] = turn['started_at']
            store.put('evidence', item['id'], item)


def chapter_owned_recaps(store):
    """The chapter recap and its questions belong to the chapter and are shown on the chapter page (ADR 0006, 0008).

    Recap turns (ids `recap:`) gain `chapter_id`; recap questions become chapter quiz questions (`origin: "chapter_quiz"`,
    keeping `tests_concept_ids`) with `chapter_id` and a `quiz_id` naming the request that made them, and recap question
    requests become chapter quiz requests. Each keeps `concept_id`, the chapter's last section when it was made, as its
    anchor for section-scoped records. The chapter is the one that now contains that section; a recap turn whose frozen
    chapter differs, or any record whose section is no longer in a chapter (moved or removed), cannot be placed: it stays
    anchored to its section, unowned, where it shows as before.
    """
    chapters = (store.get('curriculum', 'model') or {}).get('chapters') or []

    def owner(concept_id):
        return next((c['id'] for c in chapters if concept_id in c.get('concept_ids', [])), None)

    for turn in store.list('streams'):
        if not turn['id'].startswith('recap:') or turn.get('chapter_id'):
            continue
        chapter = owner(turn.get('concept_id'))
        frozen = (((turn.get('prompt_snapshot') or {}).get('context') or {}).get('chapter') or {}).get('id')
        if chapter and frozen in (None, chapter):
            turn['chapter_id'] = chapter
            store.put('streams', turn['id'], turn)
    for job in store.list('practice_jobs'):
        if job.get('purpose') != 'recap':
            continue
        job['purpose'] = 'chapter_quiz'
        chapter = owner(job.get('concept_id'))
        if chapter:
            job.update(chapter_id=chapter, quiz_id=job['id'], earlier=[])
        store.put('practice_jobs', job['id'], job)
    for task in store.list('practice_tasks'):
        if task.get('origin') != 'recap':
            continue
        task['origin'] = 'chapter_quiz'
        chapter = owner(task.get('concept_id'))
        if chapter:
            task.update(chapter_id=chapter, quiz_id=task['id'].rsplit(':', 1)[0])
        store.put('practice_tasks', task['id'], task)


def review_sets(store):
    """Review is asked for in review sets, with no schedule (ADR 0014).

    Each earlier review request (a practice job with purpose `review`, one question for one section) joins the set of the
    local day it started, `migrated-review:<date>`, a Review for me set dated by its first request; its question gains
    `set_id`, `tests_concept_ids` (its section) and `kind: "apply"`. Each chapter quiz becomes a set scoped to its
    chapter whose id is the quiz's, and its questions name it in `set_id`. Postponements ("Not now") and the daily review
    limit are dropped. Evidence is untouched.
    """
    day_of = {}
    for job in store.list('practice_jobs'):
        if job.get('purpose') != 'review' or job.get('set_id'):
            continue
        turn = store.get('streams', job['id']) or {}
        started = turn.get('started_at') if isinstance(turn.get('started_at'), (int, float)) else 0
        identifier = 'migrated-review:' + datetime.fromtimestamp(started).date().isoformat()
        found = store.get('review_sets', identifier)
        if not found or started < found['created_at']:
            store.put('review_sets', identifier, {'id': identifier, 'kind': 'for_me', 'created_at': started})
        job['set_id'] = identifier
        store.put('practice_jobs', job['id'], job)
        day_of[job['id']] = identifier
    for task in store.list('practice_tasks'):
        if task.get('set_id'):
            continue
        if task.get('origin') == 'review':
            identifier = day_of.get(task['id'].rsplit(':', 1)[0])
            if not identifier:
                identifier = 'migrated-review:' + datetime.fromtimestamp(0).date().isoformat()
                if not store.get('review_sets', identifier):
                    store.put('review_sets', identifier, {'id': identifier, 'kind': 'for_me', 'created_at': 0})
            task.update(set_id=identifier, tests_concept_ids=task.get('tests_concept_ids') or [task['concept_id']], kind='apply')
            store.put('practice_tasks', task['id'], task)
        elif task.get('origin') == 'chapter_quiz' and task.get('chapter_id') and task.get('quiz_id'):
            if not store.get('review_sets', task['quiz_id']):
                store.put('review_sets', task['quiz_id'], {'id': task['quiz_id'], 'kind': 'chapter_quiz', 'chapter_id': task['chapter_id'],
                                                           'scope': {'chapter_ids': [task['chapter_id']]}, 'created_at': task.get('created_at', 0)})
            task['set_id'] = task['quiz_id']
            store.put('practice_tasks', task['id'], task)
    for item in store.list('review_postponements'):
        store.delete('review_postponements', item['concept_id'])
    preferences = store.get('course', 'preferences')
    if preferences and 'daily_reviews' in preferences:
        store.put('course', 'preferences', {k: v for k, v in preferences.items() if k != 'daily_reviews'})


MIGRATIONS = [slim_selected_lectures, group_flat_routes, date_assessments, chapter_owned_recaps, review_sets]
VERSION = len(MIGRATIONS) + 1


def version(store):
    return (store.get('course', 'schema') or {}).get('version', 1)


def upgrade(store):
    """Bring the course to this code's version, or refuse a course written by a newer Throughline."""
    current = version(store)
    if current > VERSION:
        raise OperationError('course_too_new', f'This course was saved by a newer version of Throughline (format {current}); update Throughline to open it')
    for target in range(current + 1, VERSION + 1):
        MIGRATIONS[target - 2](store)
    if current < VERSION:
        mark_current(store)


def mark_current(store):
    store.put('course', 'schema', {'version': VERSION})
