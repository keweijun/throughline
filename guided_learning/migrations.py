"""Forward-only course migrations (ADR 0007).

A course records its format version in `course/schema`; courses without it are version 1. `upgrade` runs inside the
first operation's transaction, so a migration commits or rolls back with it. MIGRATIONS[i] moves a course from
version i + 1 to i + 2. Each migration must be idempotent and keep learning evidence and raw interactions intact.
"""
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


MIGRATIONS = [slim_selected_lectures, group_flat_routes]
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
