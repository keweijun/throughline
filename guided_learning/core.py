import uuid
from .store import OperationError

def status(store, request):
    return {'course': store.get('course', 'metadata'), 'position': store.get('course', 'position'), 'sources': store.list('sources')}

def initialize(store, request):
    if store.get('course', 'metadata') is None:
        title = request.get('title')
        if not isinstance(title, str) or not title.strip():
            raise OperationError('invalid_request', 'title must be a nonempty string')
        store.put('course', 'metadata', {'id': str(uuid.uuid4()), 'title': title})
    return status(store, request)

def save_position(store, request):
    position = request.get('position')
    if not isinstance(position, dict):
        raise OperationError('invalid_request', 'position must be an object')
    store.put('course', 'position', position)
    return {'position': position}

OPERATIONS = {'course.init': initialize, 'course.status': status, 'position.save': save_position}
