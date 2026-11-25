"""Building an outlined chapter in the app (ADR 0004): one record per chapter, internal to the host.

A record is `queued` (waiting for the learner's own requests to finish), `building` (a read-only build turn runs),
`failed` or `done`. A `building` record whose turn no longer runs reads as `interrupted` (or `failed` when the model
failed); a chapter that got built some other way reads as `done`. The chapter itself is saved through
`curriculum.chapter.save`, so the usual validation applies.
"""
import time
from . import curriculum
from .store import OperationError

NAMESPACE = 'chapter_builds'
ACTIVE = ('queued', 'building')
MAX_ATTEMPTS = 2  # the first build and one retry carrying the validation error
INTERRUPTED = 'The learning server stopped during the build; build the chapter again'


def _chapters(store):
    return curriculum.view(store, {})['chapters']


def _built(store, chapter_id):
    return any(c['id'] == chapter_id and c['concept_ids'] for c in _chapters(store))


def derive(store, record):
    """The record as the app shows it, reading the build turn's current status."""
    record = dict(record)
    if record['status'] in ACTIVE and _built(store, record['chapter_id']):
        return {**record, 'status': 'done', 'discarded': True}
    if record['status'] == 'building':
        turn = store.get('streams', record.get('turn_id') or '')
        if turn is None or turn['status'] in ('paused', 'interrupted'):
            return {**record, 'status': 'interrupted', 'error': INTERRUPTED}
        if turn['status'] == 'failed':
            return {**record, 'status': 'failed', 'error': turn.get('error') or 'The build turn failed'}
    return record


def listing(store, request):
    return {'builds': [derive(store, r) for r in sorted(store.list(NAMESPACE), key=lambda r: r.get('requested_at', 0))]}


def _record(store, chapter_id):
    record = store.get(NAMESPACE, chapter_id)
    if record is None:
        raise OperationError('unknown_build', str(chapter_id))
    return record


def ask(store, request):
    """Ask for a chapter to be built. Repeating the request while it is queued or building changes nothing."""
    chapter_id = request.get('chapter_id')
    chapters = _chapters(store)
    chapter = next((c for c in chapters if c['id'] == chapter_id), None)
    if chapter is None or chapter['concept_ids']:
        raise OperationError('not_buildable', 'Only an outlined chapter that is not built yet can be built')
    if not curriculum.view(store, {})['route']:
        raise OperationError('not_buildable', 'Build the first chapter in Codex; the app builds later chapters')
    trigger = request.get('trigger', 'learner')
    if trigger not in ('learner', 'auto'):
        raise OperationError('invalid_request', 'trigger must be learner or auto')
    for other in listing(store, {})['builds']:
        if other['status'] in ACTIVE:
            if other['chapter_id'] == chapter_id:
                return {'build': other, 'created': False}
            raise OperationError('build_busy', 'Another chapter is being built; build this one when it is ready')
    if trigger == 'auto' and store.get(NAMESPACE, chapter_id):
        # The app builds a chapter by itself once; after a failure or interruption the learner decides.
        return {'build': derive(store, store.get(NAMESPACE, chapter_id)), 'created': False}
    record = {'chapter_id': chapter_id, 'status': 'queued', 'trigger': trigger, 'requested_at': time.time(), 'attempt': 0}
    store.put(NAMESPACE, chapter_id, record)
    return {'build': record, 'created': True}


def begin(store, request):
    """Record the turn that builds a queued chapter, before the host starts it."""
    record = _record(store, request.get('chapter_id'))
    if derive(store, record)['status'] != 'queued':
        raise OperationError('invalid_transition', 'Only a queued build can begin')
    if not isinstance(request.get('turn_id'), str) or not request['turn_id']:
        raise OperationError('invalid_request', 'turn_id must be a nonempty string')
    record.update(status='building', turn_id=request['turn_id'], attempt=record['attempt'] + 1, started_at=time.time())
    store.put(NAMESPACE, record['chapter_id'], record)
    return {'build': record}


def _current(store, request):
    record = _record(store, request.get('chapter_id'))
    if record['status'] != 'building' or record.get('turn_id') != request.get('turn_id'):
        raise OperationError('stale_build', 'This build turn is no longer the current one')
    return record


def complete(store, request):
    """Save the built chapter, unless it was built some other way meanwhile; one transaction either way."""
    record = _current(store, request)
    if _built(store, record['chapter_id']):
        record.update(status='done', discarded=True, finished_at=time.time())
        store.put(NAMESPACE, record['chapter_id'], record)
        return {'build': record, 'discarded': True}
    save = {'chapter_id': record['chapter_id'], 'concepts': request.get('concepts'), 'coverage': request.get('coverage', [])}
    if isinstance(request.get('summary'), str) and request['summary'].strip():
        save['summary'] = request['summary'].strip()
    model = curriculum.chapter_save(store, save)
    record.update(status='done', finished_at=time.time())
    record.pop('retry', None)
    record.pop('error', None)
    store.put(NAMESPACE, record['chapter_id'], record)
    return {'build': record, 'discarded': False, 'chapter': next(c for c in model['chapters'] if c['id'] == record['chapter_id'])}


def reject(store, request):
    """The reply could not be saved: queue one retry carrying the error, or record the failure."""
    record = _current(store, request)
    error = str(request.get('error') or 'The build reply was rejected')
    if record['attempt'] < MAX_ATTEMPTS:
        record.update(status='queued', retry={'reply': str(request.get('reply') or ''), 'error': error})
    else:
        record.update(status='failed', error=error, finished_at=time.time())
        record.pop('retry', None)
    store.put(NAMESPACE, record['chapter_id'], record)
    return {'build': record}


OPERATIONS = {'chapter_build.list': listing, 'chapter_build.request': ask, 'chapter_build.begin': begin,
              'chapter_build.complete': complete, 'chapter_build.reject': reject}
