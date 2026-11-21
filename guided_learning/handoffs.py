"""Hand-offs to Studio (issue #229): a request a fast view cannot serve, sent to Studio as a new chat with the context of
where it was asked. The course keeps each one, so the card that sent it can say Studio is working and, once done, link
to the chat."""
import time

from .store import OperationError
from .teaching import require_text

HANDOFFS = 'studio_handoffs'
PLACES = ('drill', 'review', 'chapter', 'source', 'section', 'intro')
MAX_LABEL = 120
MAX_REQUEST = 4000


def _text(request, key, limit):
    value = request.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise OperationError('invalid_request', f'{key} is text of at most {limit} characters')
    return value.strip()


def save(store, request):
    """A hand-off just sent: where it was asked (`place`, {kind, and the ids that kind names}), what Studio will do
    (`label`), the request sent and the Studio chat it started. Saving the same id again keeps the first."""
    identifier = require_text(request, 'id')
    previous = store.get(HANDOFFS, identifier)
    if previous:
        return {'handoff': previous}
    place = request.get('place')
    if not isinstance(place, dict) or place.get('kind') not in PLACES or not all(isinstance(v, str) for v in place.values()):
        raise OperationError('invalid_request', 'place is {kind, ...ids}, kind one of ' + ', '.join(PLACES))
    value = {'id': identifier, 'place': place, 'label': _text(request, 'label', MAX_LABEL), 'request': _text(request, 'request', MAX_REQUEST),
             'thread_id': require_text(request, 'thread_id'), 'created_at': time.time()}
    return {'handoff': store.put(HANDOFFS, identifier, value)}


def listing(store, _request):
    return {'handoffs': sorted(store.list(HANDOFFS), key=lambda h: h['created_at'])}


OPERATIONS = {'handoff.save': save, 'handoff.list': listing}
