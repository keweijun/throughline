"""Course changes the teacher suggests making in Studio (ADR 0016).

When the teacher judges that changing the course itself would help (a prerequisite the route lacks, a section the
learner keeps finding too fast, a request in Questions to change the course), a lesson or side-question reply carries
one suggestion. The learner opens it in Studio with the request filled in, or dismisses it. One is open at a time: a
new suggestion supersedes any still open. The teacher is shown earlier suggestions, so it does not repeat them."""
import re
import time
from .store import OperationError
from .teaching import require_text, validate_concept

NOTE = re.compile(r'<course-change>\s*(\{.*?\})\s*</course-change>', re.S)
MAX_TEXT = 300
RESOLVED = ('dismissed', 'opened')
RECENT = 10  # earlier suggestions the teacher is shown


def _all(store):
    return sorted(store.list('course_change'), key=lambda c: c['created_at'])


def suggest(store, request):
    """Record the suggestion a reply carried; the same turn completing again records nothing new."""
    turn_id = require_text(request, 'turn_id')
    concept_id = require_text(request, 'concept_id')
    validate_concept(store, concept_id)
    text = require_text(request, 'request').strip()
    if len(text) > MAX_TEXT:
        raise OperationError('invalid_request', f'request must be at most {MAX_TEXT} characters')
    known = store.get('course_change', turn_id)
    if known:
        return {'change': known}
    now = time.time()
    for change in _all(store):
        if change['status'] == 'suggested':
            store.put('course_change', change['id'], {**change, 'status': 'superseded', 'updated_at': now})
    change = {'id': turn_id, 'concept_id': concept_id, 'request': text, 'status': 'suggested', 'created_at': now, 'updated_at': now}
    return {'change': store.put('course_change', turn_id, change)}


def resolve(store, request):
    """The learner opened the suggestion in Studio or dismissed it; either way it is no longer shown."""
    change = store.get('course_change', require_text(request, 'id'))
    if not change:
        raise OperationError('unknown_course_change', str(request.get('id')))
    status = request.get('status')
    if status not in RESOLVED:
        raise OperationError('invalid_request', 'status must be one of ' + ', '.join(RESOLVED))
    return {'change': store.put('course_change', change['id'], {**change, 'status': status, 'updated_at': time.time()})}


def listing(store, request):
    """The open suggestion, if any; a course saved before suggestions existed has none."""
    return {'changes': [c for c in _all(store) if c['status'] == 'suggested']}


def history(store, request):
    """Earlier suggestions with what became of them, for the teacher's context."""
    return {'changes': [{'request': c['request'], 'status': c['status']} for c in _all(store)[-RECENT:]]}


OPERATIONS = {'course_change.suggest': suggest, 'course_change.resolve': resolve, 'course_change.list': listing,
              'course_change.history': history}
