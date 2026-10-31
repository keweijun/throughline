"""Course-owned presentation preferences, separate from learning evidence."""
from .store import OperationError


LANGUAGES = {'en': 'English', 'zh-CN': 'Simplified Chinese'}
DEFAULTS = {'language': 'en'}


def validate_language(value):
    if not isinstance(value, str) or value not in LANGUAGES:
        raise OperationError('invalid_language', 'Choose English or Simplified Chinese')
    return value


def view(store, request):
    # A course saved while review had a daily limit may still store it (ADR 0014); it is no longer a preference.
    stored = {k: v for k, v in store.get('course', 'preferences', {}).items() if k in DEFAULTS}
    return {'preferences': {**DEFAULTS, **stored}}


def save(store, request):
    """Save the preferences given; the others keep their value."""
    changes = {}
    if 'language' in request:
        changes['language'] = validate_language(request['language'])
    if not changes:
        raise OperationError('invalid_request', 'Give language')
    store.put('course', 'preferences', {**view(store, request)['preferences'], **changes})
    return view(store, request)


OPERATIONS = {'preferences.view': view, 'preferences.save': save}
