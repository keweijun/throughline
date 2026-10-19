from importlib import import_module
from .store import Store, OperationError

# Add operation modules here; each exports OPERATIONS: name -> (store, request).
MODULES = ('core', 'sources', 'curriculum', 'teaching', 'evidence', 'background', 'streaming', 'practice')

def execute(workspace, request):
    if not isinstance(request, dict) or not isinstance(request.get('op'), str):
        raise OperationError('invalid_request', 'Request must be an object with an op string')
    operations = {}
    for name in MODULES:
        operations.update(import_module(f'.{name}', __package__).OPERATIONS)
    handler = operations.get(request['op'])
    if handler is None:
        raise OperationError('unknown_operation', request['op'])
    store = Store(workspace)
    try:
        with store.db:
            store.db.execute('BEGIN IMMEDIATE')
            if request['op'] != 'course.init' and store.get('course', 'metadata') is None:
                raise OperationError('course_not_initialized', 'Run course.init first')
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
    finally:
        store.db.close()
