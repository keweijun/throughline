"""Course-owned presentation preferences, separate from learning evidence."""
from .store import OperationError


LANGUAGES = {'en': 'English', 'zh-CN': 'Simplified Chinese'}
# At most this many reviews a day (ADR 0008); a course saved before the setting existed reads the default.
DAILY_REVIEWS = 5
MAX_DAILY_REVIEWS = 20
DEFAULTS = {'language': 'en', 'daily_reviews': DAILY_REVIEWS}


def validate_language(value):
    if not isinstance(value, str) or value not in LANGUAGES:
        raise OperationError('invalid_language', 'Choose English or Simplified Chinese')
    return value


def validate_daily_reviews(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_DAILY_REVIEWS:
        raise OperationError('invalid_daily_reviews', f'Daily reviews must be a whole number from 1 to {MAX_DAILY_REVIEWS}')
    return value


def view(store, request):
    return {'preferences': {**DEFAULTS, **store.get('course', 'preferences', {})}}


def save(store, request):
    """Save the preferences given; the others keep their value."""
    changes = {}
    if 'language' in request:
        changes['language'] = validate_language(request['language'])
    if 'daily_reviews' in request:
        changes['daily_reviews'] = validate_daily_reviews(request['daily_reviews'])
    if not changes:
        raise OperationError('invalid_request', 'Give language or daily_reviews')
    store.put('course', 'preferences', {**view(store, request)['preferences'], **changes})
    return view(store, request)


OPERATIONS = {'preferences.view': view, 'preferences.save': save}
