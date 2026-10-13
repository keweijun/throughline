from importlib import import_module
from .store import Store, OperationError

# Add operation modules here; each exports OPERATIONS: name -> (store, request).
MODULES = ('core', 'sources', 'curriculum', 'teaching', 'evidence')

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
            return handler(store, request)
    finally:
        store.db.close()

