"""Course memory (ADR 0010): confirmed preferences, taught terms and difficulties the teacher keeps about one course.
Entries are facts citing the interactions behind them; they are never evidence and never come from learner annotations."""
import re
import time
import unicodedata
from .store import OperationError
from .preferences import view as course_preferences
from .teaching import require_text, validate_concept, record_interaction

KINDS = ('preference', 'taught_term', 'difficulty')
IN_EFFECT = ('active', 'suggested', 'confirmed')  # what a new entry saying the same thing merges into
LIVE = IN_EFFECT + ('cleared',)  # the rest are deleted, merged or pruned
MAX_TEXT = 300
NOTE = re.compile(r'<course-memory>\s*(\{.*?\})\s*</course-memory>', re.S)


def strip(text):
    """Text as the learner sees it: without the teacher's memory note or suggested course change."""
    return re.sub(r'\s*<(course-memory|course-change)>.*?(</\1>|$)', '', text or '', flags=re.S)


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
    return {'entries': [e for e in _entries(store) if e['status'] in LIVE]}


def for_prompt(store):
    """What the teacher may rely on: confirmed preferences, taught terms and current difficulties."""
    entries = view(store, {})['entries']
    memory = {'preferences': [e['text'] for e in entries if e['kind'] == 'preference' and e['status'] == 'confirmed'],
              'taught_terms': [{'term': e['text'], 'concept_id': e['concept_id']} for e in entries if e['kind'] == 'taught_term'],
              'difficulties': [{'id': e['id'], 'idea': e['text']} for e in entries if e['kind'] == 'difficulty' and e['status'] == 'active']}
    return {k: v for k, v in memory.items() if v}


def prompt(store, request):
    return {'memory': for_prompt(store)}


def _create(store, identifier, kind, text, concept_id, interaction_ids, teacher=False):
    """Adds an entry, merges it into a live one saying the same thing, or refuses it when a deleted entry of the kind
    cites any of the same interactions or, for the teacher's notes, says the same thing. Returns (entry, recorded)."""
    key = text.casefold()
    for entry in _entries(store):
        if entry['kind'] != kind:
            continue
        if entry['status'] == 'deleted' and (set(entry['interaction_ids']) & set(interaction_ids) or teacher and entry['text'].casefold() == key):
            return entry, False
        if entry['status'] in IN_EFFECT and entry['text'].casefold() == key:
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
    if not entry or entry['status'] not in LIVE:
        raise OperationError('unknown_memory_entry', request['id'])
    return entry


def save(store, request):
    """The learner edits an entry's text; a new id with a kind adds an entry. A preference may leave out `concept_id`: one
    stated while the course was built belongs to no section."""
    identifier = require_text(request, 'id')
    text = _text(request.get('text'))
    if store.get('memory', identifier):
        entry = _live(store, request)
        return {'entry': store.put('memory', identifier, {**entry, 'text': text, 'updated_at': time.time()})}
    if request.get('kind') not in KINDS:
        raise OperationError('invalid_request', 'kind must be preference, taught_term or difficulty')
    concept_id = None if request['kind'] == 'preference' and not request.get('concept_id') else require_text(request, 'concept_id')
    if concept_id:
        validate_concept(store, concept_id)
    entry, recorded = _create(store, identifier, request['kind'], text, concept_id, _ids(store, request.get('interaction_ids', [])))
    if not recorded:
        raise OperationError('memory_exists', 'The course memory already has or deleted this entry')
    return {'entry': entry}


def delete(store, request):
    """Final: the entry stays as a tombstone so neither the same interactions nor a later note with its text bring it back."""
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
        entry, created = _create(store, f'{turn_id}:{index}', item['kind'], text, concept_id, list(dict.fromkeys(cited + own)), teacher=True)
        (recorded if created else skipped).append(entry if created else {'text': text, 'reason': 'deleted' if entry['status'] == 'deleted' else 'exists'})
    for identifier in value.get('cleared', []):
        entry = store.get('memory', identifier) if isinstance(identifier, str) else None
        if entry and entry['kind'] == 'difficulty' and entry['status'] == 'active':
            store.put('memory', identifier, {**entry, 'status': 'cleared', 'cleared_by': own, 'updated_at': time.time()})
    store.put('memory_notes', turn_id, {'turn_id': turn_id, 'recorded': [e['id'] for e in recorded]})
    return {'recorded': recorded, 'skipped': skipped}


# The preference a repeated skip reason suggests, in each teaching language (ADR 0011). Its keys are the skip reasons
# (practice.SKIP_REASONS); web/src/lib/types.ts mirrors them as SkipReason.
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


def idea_key(text):
    """When two check questions test the same idea: their `idea` texts match ignoring case, punctuation and spacing."""
    return ' '.join(re.sub(r'[\W_]+', ' ', unicodedata.normalize('NFKC', text).casefold()).split())


def from_check(store, concept_id, idea):
    """Keeps difficulties in step with check answers on one idea, after a check answer is recorded (ADR 0010). A correct
    answer clears the active difficulties on the idea: those whose text has its key or that cite a check answer on it.
    A miss (wrong or unsure) joins such a difficulty, or else creates one once two misses since the latest correct
    answer on the idea are not cited by any difficulty, so a deleted one comes back only from new misses."""
    key = idea_key(idea)
    answers = sorted((s['answer'] for lesson in store.list('lessons') for s in lesson['steps']
                      if s.get('answer') and s.get('check') and idea_key(s['check']['idea']) == key), key=lambda a: a['answered_at'])
    latest, on_idea = answers[-1], {a['interaction_id'] for a in answers}
    difficulties = [e for e in _entries(store) if e['kind'] == 'difficulty']
    current = [e for e in difficulties if e['status'] == 'active' and (idea_key(e['text']) == key or on_idea & set(e['interaction_ids']))]
    now = time.time()
    if latest['correct']:
        for entry in current:
            store.put('memory', entry['id'], {**entry, 'status': 'cleared', 'cleared_by': [latest['interaction_id']], 'updated_at': now})
        return
    if current:
        entry = current[0]
        if latest['interaction_id'] not in entry['interaction_ids']:
            store.put('memory', entry['id'], {**entry, 'interaction_ids': entry['interaction_ids'] + [latest['interaction_id']], 'updated_at': now})
        return
    cited = {i for e in difficulties for i in e['interaction_ids']}
    misses = []
    for answer in reversed(answers):
        if answer['correct']:
            break
        if answer['interaction_id'] not in cited:
            misses.insert(0, answer['interaction_id'])
    if len(misses) >= 2:
        _create(store, 'check:' + latest['interaction_id'], 'difficulty', _text(idea), concept_id, misses)


def _refuse(message):
    raise OperationError('invalid_consolidation', message)


def consolidate(store, request):
    """Applies a section-end consolidation once per turn: `merge` folds duplicate entries into one, which keeps its text and
    gains their interactions; `prune` retires cleared or stale entries with a reason. It never adds or rewords an entry,
    touches a deleted one or retires a confirmed preference, which only the learner can delete. Refused whole."""
    turn_id = require_text(request, 'turn_id')
    concept_id = require_text(request, 'concept_id')
    validate_concept(store, concept_id)
    if store.get('memory_consolidations', turn_id):
        return {'changed': [], 'replayed': True}
    reply = request.get('reply')
    if not isinstance(reply, dict) or set(reply) - {'merge', 'prune'}:
        _refuse('A consolidation is an object with only merge and prune lists')
    merges, prunes = reply.get('merge', []), reply.get('prune', [])
    if not isinstance(merges, list) or not isinstance(prunes, list):
        _refuse('merge and prune must be lists')
    changed = []

    def live(identifier):
        entry = store.get('memory', identifier) if isinstance(identifier, str) else None
        if not entry or entry['status'] not in LIVE:
            _refuse(f'{identifier} is not a live memory entry')
        if identifier in changed:
            _refuse(f'{identifier} is changed twice')
        changed.append(identifier)
        return entry

    merged = []
    for item in merges:
        if not isinstance(item, dict) or set(item) != {'into', 'entries'} or not isinstance(item['entries'], list) or not item['entries']:
            _refuse('Each merge is {into, entries} with at least one entry to fold in')
        into = live(item['into'])
        others = [live(i) for i in item['entries']]
        # Same status too, so a suggested preference never merges into, or out of, a confirmed one.
        if any((e['kind'], e['status']) != (into['kind'], into['status']) for e in others):
            _refuse('Only entries of the same kind and status merge')
        merged.append((into, others))
    pruned = []
    for item in prunes:
        if not isinstance(item, dict) or not isinstance(item.get('reason'), str) or not item['reason'].strip():
            _refuse('Each prune is {id, reason}')
        entry = live(item.get('id'))
        if entry['kind'] == 'preference' and entry['status'] == 'confirmed':
            _refuse('A confirmed preference is removed only by the learner')
        pruned.append((entry, ' '.join(item['reason'].split())[:MAX_TEXT]))
    now = time.time()
    for into, others in merged:
        ids = list(dict.fromkeys(into['interaction_ids'] + [i for e in others for i in e['interaction_ids']]))
        skips = list(dict.fromkeys(into.get('skip_ids', []) + [i for e in others for i in e.get('skip_ids', [])]))
        store.put('memory', into['id'], {**into, 'interaction_ids': ids, **({'skip_ids': skips} if skips else {}), 'consolidated_by': turn_id, 'updated_at': now})
        for entry in others:
            store.put('memory', entry['id'], {**entry, 'status': 'merged', 'merged_into': into['id'], 'consolidated_by': turn_id, 'updated_at': now})
    for entry, reason in pruned:
        store.put('memory', entry['id'], {**entry, 'status': 'pruned', 'pruned_reason': reason, 'consolidated_by': turn_id, 'updated_at': now})
    store.put('memory_consolidations', turn_id, {
        'turn_id': turn_id, 'concept_id': concept_id, 'created_at': now,
        'merge': [{'into': into['id'], 'entries': [e['id'] for e in others]} for into, others in merged],
        'prune': [{'id': entry['id'], 'reason': reason} for entry, reason in pruned]})
    return {'changed': changed}


def consolidations(store, request):
    return {'consolidations': sorted(store.list('memory_consolidations'), key=lambda c: c['created_at'])}


def request(store, request):
    """The learner says, in their own words, what the teacher should remember about how they like to be taught. The
    message is an interaction, so the preferences it leads to cite it; the reply comes from a `memory` turn."""
    identifier = require_text(request, 'id')
    concept_id = require_text(request, 'concept_id')
    validate_concept(store, concept_id)
    text = require_text(request, 'text').strip()
    existing = store.get('memory_requests', identifier)
    if existing:
        return {'request': existing, 'created': False}
    record_interaction(store, {'id': 'memory-request:' + identifier, 'role': 'user', 'text': text, 'concept_id': concept_id})
    return {'request': store.put('memory_requests', identifier, {'id': identifier, 'text': text, 'concept_id': concept_id,
                                                                 'turn_id': 'memory-' + identifier, 'created_at': time.time()}),
            'created': True}


def requests(store, request):
    return {'requests': sorted(store.list('memory_requests'), key=lambda r: r['created_at'])}


def answer(store, request):
    """Applies the reply to a memory request once: `remember` adds preferences, confirmed since the learner asked for
    them, and `forget` deletes listed preferences (final, as when the learner deletes one). A malformed reply changes no
    entry; the request keeps why it was refused."""
    identifier = require_text(request, 'id')
    record = store.get('memory_requests', identifier)
    if not record:
        raise OperationError('unknown_memory_request', identifier)
    if 'reply' in record:
        return {'request': record, 'replayed': True}
    reply = request.get('reply')
    live = {e['id']: e for e in _entries(store) if e['kind'] == 'preference' and e['status'] in IN_EFFECT}
    try:
        if not isinstance(reply, dict) or set(reply) - {'reply', 'remember', 'forget'} or not isinstance(reply.get('reply'), str) or not reply['reply'].strip():
            raise OperationError('invalid_memory_reply', 'A memory reply is an object with reply, remember and forget')
        remember = [_text(t) for t in _list(reply.get('remember', []))]
        forget = _list(reply.get('forget', []))
        if any(i not in live for i in forget):
            raise OperationError('invalid_memory_reply', 'forget names only listed preferences')
    except OperationError as error:
        return {'request': store.put('memory_requests', identifier, {**record, 'error': str(error)}), 'refused': True}
    cited = ['memory-request:' + identifier]
    remembered = []
    for index, text in enumerate(remember):
        entry, _ = _create(store, f"{record['turn_id']}:{index}", 'preference', text, None, cited)
        if entry['status'] != 'deleted':
            entry = store.put('memory', entry['id'], {**entry, 'status': 'confirmed', 'updated_at': time.time()})
            remembered.append(entry['id'])
    for entry_id in forget:
        store.put('memory', entry_id, {**live[entry_id], 'status': 'deleted', 'updated_at': time.time()})
    return {'request': store.put('memory_requests', identifier, {**record, 'reply': reply['reply'].strip(), 'remembered': remembered,
                                                                 'forgotten': forget, 'answered_at': time.time()})}


def _list(value):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise OperationError('invalid_memory_reply', 'remember and forget are lists of strings')
    return list(dict.fromkeys(value))


OPERATIONS = {'memory.consolidate': consolidate, 'memory.consolidations': consolidations,
              'memory.view': view, 'memory.save': save, 'memory.delete': delete, 'memory.confirm': confirm, 'memory.note': note,
              'memory.prompt': prompt, 'memory.request': request, 'memory.requests': requests, 'memory.answer': answer}
