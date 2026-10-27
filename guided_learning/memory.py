"""Course memory (ADR 0010): confirmed preferences, taught terms and difficulties the teacher keeps about one course.
Entries are facts citing the interactions behind them; they are never evidence and never come from learner annotations."""
import re
import time
from .store import OperationError
from .preferences import view as course_preferences
from .teaching import require_text, validate_concept

KINDS = ('preference', 'taught_term', 'difficulty')
MAX_TEXT = 300
NOTE = re.compile(r'<course-memory>\s*(\{.*?\})\s*</course-memory>', re.S)


def strip(text):
    """Text as the learner sees it: without the teacher's memory note."""
    return re.sub(r'\s*<course-memory>.*?(</course-memory>|$)', '', text or '', flags=re.S)


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise OperationError('invalid_request', 'A memory entry needs text')
    value = ' '.join(value.split())
    if len(value) > MAX_TEXT:
        raise OperationError('invalid_request', f'A memory entry is at most {MAX_TEXT} characters')
    return value


def _ids(store, value):
    if not isinstance(value, list):
        raise OperationError('invalid_request', 'interaction_ids must be a list')
    return [i for i in dict.fromkeys(value) if isinstance(i, str) and store.get('interactions', i)]


def _entries(store):
    return sorted(store.list('memory'), key=lambda e: e['created_at'])


def view(store, request):
    return {'entries': [e for e in _entries(store) if e['status'] != 'deleted']}


def for_prompt(store):
    """What the teacher may rely on: confirmed preferences, taught terms and current difficulties."""
    entries = view(store, {})['entries']
    memory = {'preferences': [e['text'] for e in entries if e['kind'] == 'preference' and e['status'] == 'confirmed'],
              'taught_terms': [{'term': e['text'], 'concept_id': e['concept_id']} for e in entries if e['kind'] == 'taught_term'],
              'difficulties': [{'id': e['id'], 'idea': e['text']} for e in entries if e['kind'] == 'difficulty' and e['status'] == 'active']}
    return {k: v for k, v in memory.items() if v}


def _create(store, identifier, kind, text, concept_id, interaction_ids):
    """Adds an entry, merges it into a live one saying the same thing, or refuses it when a deleted entry of the kind
    cites any of the same interactions. Returns (entry, recorded)."""
    key = text.casefold()
    for entry in _entries(store):
        if entry['kind'] != kind:
            continue
        if entry['status'] == 'deleted' and set(entry['interaction_ids']) & set(interaction_ids):
            return entry, False
        if entry['status'] in ('active', 'suggested', 'confirmed') and entry['text'].casefold() == key:
            merged = list(dict.fromkeys(entry['interaction_ids'] + interaction_ids))
            if merged != entry['interaction_ids']:
                store.put('memory', entry['id'], {**entry, 'interaction_ids': merged, 'updated_at': time.time()})
            return entry, False
    now = time.time()
    entry = {'id': identifier, 'kind': kind, 'text': text, 'status': 'suggested' if kind == 'preference' else 'active',
             'concept_id': concept_id, 'interaction_ids': interaction_ids, 'created_at': now, 'updated_at': now}
    return store.put('memory', identifier, entry), True


def _live(store, request):
    entry = store.get('memory', require_text(request, 'id'))
    if not entry or entry['status'] == 'deleted':
        raise OperationError('unknown_memory_entry', request['id'])
    return entry


def save(store, request):
    """The learner edits an entry's text; a new id with a kind adds an entry."""
    identifier = require_text(request, 'id')
    text = _text(request.get('text'))
    if store.get('memory', identifier):
        entry = _live(store, request)
        return {'entry': store.put('memory', identifier, {**entry, 'text': text, 'updated_at': time.time()})}
    if request.get('kind') not in KINDS:
        raise OperationError('invalid_request', 'kind must be preference, taught_term or difficulty')
    concept_id = require_text(request, 'concept_id')
    validate_concept(store, concept_id)
    entry, recorded = _create(store, identifier, request['kind'], text, concept_id, _ids(store, request.get('interaction_ids', [])))
    if not recorded:
        raise OperationError('memory_exists', 'The course memory already has or deleted this entry')
    return {'entry': entry}


def delete(store, request):
    """Final: the entry stays as a tombstone so the same interactions cannot bring it back."""
    entry = _live(store, request)
    store.put('memory', entry['id'], {**entry, 'status': 'deleted', 'updated_at': time.time()})
    return {'deleted': entry['id']}


def confirm(store, request):
    entry = _live(store, request)
    if entry['kind'] != 'preference':
        raise OperationError('invalid_request', 'Only a suggested preference is confirmed')
    return {'entry': store.put('memory', entry['id'], {**entry, 'status': 'confirmed', 'updated_at': time.time()})}


def note(store, request):
    """Records the memory note a teaching turn ended with, once per turn. The turn's own interactions are cited with any
    earlier ones the note names; entries of unknown kinds are skipped, a malformed note is refused whole."""
    turn_id = require_text(request, 'turn_id')
    concept_id = require_text(request, 'concept_id')
    validate_concept(store, concept_id)
    value = request.get('note')
    if not isinstance(value, dict) or not isinstance(value.get('entries', []), list) or not isinstance(value.get('cleared', []), list):
        raise OperationError('invalid_request', 'A memory note is an object with entries and cleared lists')
    if store.get('memory_notes', turn_id):
        return {'recorded': [], 'skipped': [], 'replayed': True}
    own = _ids(store, request.get('interaction_ids', []))
    items = []
    for index, item in enumerate(value.get('entries', [])):
        if not isinstance(item, dict):
            raise OperationError('invalid_request', 'Each memory entry is an object')
        items.append((index, item, _text(item.get('text')), _ids(store, item.get('interaction_ids', []))))
    recorded, skipped = [], []
    for index, item, text, cited in items:
        if item.get('kind') not in KINDS:
            skipped.append({'text': text, 'reason': 'unknown_kind'})
            continue
        entry, created = _create(store, f'{turn_id}:{index}', item['kind'], text, concept_id, list(dict.fromkeys(cited + own)))
        (recorded if created else skipped).append(entry if created else {'text': text, 'reason': 'deleted' if entry['status'] == 'deleted' else 'exists'})
    for identifier in value.get('cleared', []):
        entry = store.get('memory', identifier) if isinstance(identifier, str) else None
        if entry and entry['kind'] == 'difficulty' and entry['status'] == 'active':
            store.put('memory', identifier, {**entry, 'status': 'cleared', 'cleared_by': own, 'updated_at': time.time()})
    store.put('memory_notes', turn_id, {'turn_id': turn_id, 'recorded': [e['id'] for e in recorded]})
    return {'recorded': recorded, 'skipped': skipped}


# The preference a repeated skip reason suggests, in each teaching language (ADR 0011).
SKIP_PREFERENCES = {'en': {'too_easy': 'Harder exercises, without routine ones', 'too_tedious': 'Fewer long calculations',
                           'not_relevant': 'Only exercises relevant to my goals'},
                    'zh-CN': {'too_easy': '练习难一些，少出常规题', 'too_tedious': '少一些冗长的计算',
                              'not_relevant': '只出与我的学习目标相关的练习'}}


def suggest_from_skips(store, reason, concept_id):
    """Once two exercises are skipped with the same reason, suggests the matching preference citing those skips
    (`skip_ids`, task IDs: a skip has no interaction). A preference already suggested, confirmed or deleted for that
    reason or with the same text is not suggested again; a live one cites the new skip."""
    skips = [t['id'] for t in sorted(store.list('practice_tasks'), key=lambda t: t.get('skipped_at', 0))
             if t.get('status') == 'skipped' and t.get('skip_reason') == reason]
    text = SKIP_PREFERENCES[course_preferences(store, {})['preferences']['language']][reason]
    for entry in _entries(store):
        if entry['kind'] == 'preference' and (entry.get('skip_reason') == reason or entry['text'].casefold() == text.casefold()):
            cited = list(dict.fromkeys(entry.get('skip_ids', []) + skips))
            if entry['status'] != 'deleted' and cited != entry.get('skip_ids'):
                store.put('memory', entry['id'], {**entry, 'skip_ids': cited, 'updated_at': time.time()})
            return None
    if len(skips) < 2:
        return None
    now = time.time()
    return store.put('memory', 'skip:' + reason, {'id': 'skip:' + reason, 'kind': 'preference', 'text': text, 'status': 'suggested',
                                                 'concept_id': concept_id, 'interaction_ids': [], 'skip_ids': skips,
                                                 'skip_reason': reason, 'created_at': now, 'updated_at': now})


OPERATIONS = {'memory.view': view, 'memory.save': save, 'memory.delete': delete, 'memory.confirm': confirm, 'memory.note': note,
              'memory.prompt': lambda store, request: {'memory': for_prompt(store)}}
