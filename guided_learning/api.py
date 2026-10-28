import sqlite3
from importlib import import_module
from . import migrations
from .store import Store, OperationError

# Add operation modules here; each exports OPERATIONS: name -> (store, request).
MODULES = ('core', 'sources', 'curriculum', 'teaching', 'evidence', 'background', 'streaming', 'branches', 'practice', 'preparation', 'preferences', 'annotations', 'chapter_builds', 'review', 'memory', 'lessons', 'widgets')

# Operations that only read run without the write lock, beside a writer. One that writes after all is run again as a write.
READS = {'annotations.list', 'background.view', 'branch.list', 'branch.read', 'chapter_build.list', 'course.status',
         'curriculum.chapter.view', 'curriculum.check', 'curriculum.context', 'curriculum.coverage', 'curriculum.view',
         'deferred.list', 'evidence.unresolved', 'evidence.view', 'interaction.read', 'lesson.list', 'lesson.read',
         'memory.consolidations', 'memory.prompt', 'memory.view', 'practice.list', 'preferences.view', 'review.schedule',
         'session.resume', 'source.read', 'source.units', 'stream.list', 'stream.read', 'stream.summaries',
         'widgets.list'}


class _NeedsWrite(Exception):
    pass


def execute(workspace, request):
    if not isinstance(request, dict) or not isinstance(request.get('op'), str):
        raise OperationError('invalid_request', 'Request must be an object with an op string')
    operations = {}
    for name in MODULES:
        operations.update(import_module(f'.{name}', __package__).OPERATIONS)
    handler = operations.get(request['op'])
    if handler is None:
        raise OperationError('unknown_operation', request['op'])
    store = Store(workspace, create=request['op'] == 'course.init')
    try:
        if request['op'] in READS:
            try:
                return _read(store, handler, request)
            except _NeedsWrite:
                pass
        return _write(store, handler, request)
    finally:
        store.db.close()


def _read(store, handler, request):
    store.db.execute('PRAGMA query_only=1')
    try:
        with store.db:
            store.db.execute('BEGIN')
            if store.get('course', 'metadata') is None:
                raise OperationError('course_not_initialized', 'Run course.init first')
            if migrations.version(store) != migrations.VERSION:
                raise _NeedsWrite  # to migrate, or to refuse a newer course
            try:
                return handler(store, request)
            except sqlite3.OperationalError as exc:
                if 'readonly' in str(exc):
                    raise _NeedsWrite
                raise
    finally:
        store.db.execute('PRAGMA query_only=0')


def _write(store, handler, request):
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        if store.get('course', 'metadata') is None:
            if request['op'] != 'course.init':
                raise OperationError('course_not_initialized', 'Run course.init first')
            result = handler(store, request)
            migrations.mark_current(store)
            return result
        migrations.upgrade(store)
        if request['op'] in ('position.save', 'mainline.enter'):
            request_id = request.get('request_id')
            if not isinstance(request_id, str) or not request_id.strip():
                raise OperationError('invalid_request', 'Checkpoint mutations require request_id')
            receipt = store.get('checkpoint_receipts', request_id)
            if receipt:
                if receipt['request'] != request:
                    raise OperationError('id_conflict', request_id)
                return {'replayed': True, 'position': store.get('course', 'position'), 'original_result': receipt['result']}
            result = handler(store, request)
            store.put('checkpoint_receipts', request_id, {'request': request, 'result': result})
            return {**result, 'replayed': False}
        return handler(store, request)
