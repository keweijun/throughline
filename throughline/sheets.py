"""Sheets (issue #229): a page Codex writes in Studio for review, such as a cheat sheet, a formula sheet or "my mistakes on
one page", in Markdown with LaTeX and the course's widgets. A sheet covers chapters or sections; the Review place shows
it when its scope meets the learner's, and so does the chapter page of a chapter it covers. Codex rewrites a sheet by
saving it again under its id."""
import time

from . import curriculum, handoffs
from .store import OperationError
from .teaching import require_text

SHEETS = 'sheets'
MAX_TITLE = 200
MAX_MARKDOWN = 60000


def _scope(store, value):
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - {'chapter_ids', 'concept_ids'} or not all(
            isinstance(value.get(k, []), list) and all(isinstance(i, str) for i in value.get(k, [])) for k in ('chapter_ids', 'concept_ids')):
        raise OperationError('invalid_request', 'scope lists chapter_ids and concept_ids')
    model = curriculum.model(store)
    chapters, route = {c['id'] for c in model['chapters']}, set(model['route'])
    unknown = [i for i in value.get('chapter_ids', []) if i not in chapters] + [i for i in value.get('concept_ids', []) if i not in route]
    if unknown:
        raise OperationError('unknown_concept', 'Not in this course: ' + ', '.join(unknown))
    return {k: list(dict.fromkeys(value[k])) for k in ('chapter_ids', 'concept_ids') if value.get(k)}


def save(store, request):
    """Save a sheet, or replace the one with this id: `title`, `markdown` and the `scope` it covers (chapters or
    sections; none means the whole course). `handoff_id` links it to the hand-off that asked for it."""
    identifier = require_text(request, 'id')
    title = request.get('title')
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > MAX_TITLE:
        raise OperationError('invalid_request', f'title is text of at most {MAX_TITLE} characters')
    markdown = request.get('markdown')
    if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > MAX_MARKDOWN:
        raise OperationError('invalid_request', f'markdown is text of at most {MAX_MARKDOWN} characters')
    previous = store.get(SHEETS, identifier) or {}
    now = time.time()
    value = {'id': identifier, 'title': title.strip(), 'markdown': markdown.strip(), 'scope': _scope(store, request.get('scope')),
             'created_at': previous.get('created_at', now), 'updated_at': now}
    store.put(SHEETS, identifier, value)
    handoffs.record_result(store, request.get('handoff_id'), {'kind': 'sheet', 'id': identifier, 'title': value['title']})
    return {'sheet': value}


def listing(store, _request):
    """Every sheet, most recently written first."""
    return {'sheets': sorted(store.list(SHEETS), key=lambda s: -s['updated_at'])}


def delete(store, request):
    """The learner removes a sheet they no longer want; Codex can write it again."""
    identifier = require_text(request, 'id')
    if store.get(SHEETS, identifier) is None:
        raise OperationError('unknown_sheet', identifier)
    store.delete(SHEETS, identifier)
    return {'deleted': identifier}


OPERATIONS = {'sheet.save': save, 'sheet.list': listing, 'sheet.delete': delete}
