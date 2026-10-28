import uuid
from .store import OperationError

DEPTHS = ('overview', 'standard', 'rigorous')
LEVELS = ('none', 'some', 'solid')


def status(store, request):
    return {'course': store.get('course', 'metadata'), 'position': store.get('course', 'position'), 'sources': store.list('sources'),
            'profile': store.get('course', 'profile')}


def save_profile(store, request):
    """What the learner told Codex while the course was built: goal, depth, prior knowledge and focus. A prerequisite's
    optional `check` says what a quick check in that interview showed. Never evidence of mastery."""
    profile = request.get('profile')
    if not isinstance(profile, dict) or not str(profile.get('goal', '')).strip():
        raise OperationError('invalid_profile', 'profile must be an object with a nonempty goal')
    if profile.get('depth') not in DEPTHS:
        raise OperationError('invalid_profile', 'depth must be overview, standard or rigorous')
    prerequisites = profile.get('prerequisites', [])
    if not isinstance(prerequisites, list) or any(not isinstance(p, dict) or not str(p.get('topic', '')).strip() or p.get('level') not in LEVELS for p in prerequisites):
        raise OperationError('invalid_profile', 'each prerequisite needs a topic and a level of none, some or solid')
    clean = {'goal': str(profile['goal']).strip(), 'depth': profile['depth'],
             'prerequisites': [{'topic': str(p['topic']).strip(), 'level': p['level'],
                                **({'check': str(p['check']).strip()} if str(p.get('check', '')).strip() else {})} for p in prerequisites]}
    for field in ('focus', 'notes'):
        if str(profile.get(field, '')).strip():
            clean[field] = str(profile[field]).strip()
    store.put('course', 'profile', clean)
    return {'profile': clean}

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

OPERATIONS = {'course.init': initialize, 'course.status': status, 'course.profile.save': save_profile, 'position.save': save_position}
