"""Course-owned presentation preferences, separate from learning evidence."""
from .store import OperationError


LANGUAGES = {'en': 'English', 'zh-CN': 'Simplified Chinese'}


def validate_language(value):
    if not isinstance(value, str) or value not in LANGUAGES:
        raise OperationError('invalid_language', 'Choose English or Simplified Chinese')
    return value


def view(store, request):
    return {'preferences': store.get('course', 'preferences', {'language': 'en'})}


def save(store, request):
    language = validate_language(request.get('language'))
    store.put('course', 'preferences', {'language': language})
    return view(store, request)


OPERATIONS = {'preferences.view': view, 'preferences.save': save}
