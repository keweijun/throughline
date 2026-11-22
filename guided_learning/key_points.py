"""Key points (ADR 0024): what a learner should hold from each studied section, written by the teacher and never edited
by the learner, who asks Codex to change them. The lesson's last step writes a section's points; an idle job writes them
for sections studied before, and a short paragraph per chapter saying how its sections' points connect. They replace the
chapter recap (ADR 0006)."""
import hashlib
import json
import time

from . import curriculum, streaming
from .store import OperationError
from .teaching import require_text, validate_concept

POINTS = 'key_points'
SHEETS = 'chapter_sheets'
MAX_POINTS = 12  # a sanity cap per section; the teacher decides how many the section needs
MAX_TEXT = 1200
MAX_REQUEST = 1000
MAX_CONNECTION = 4000
FIELDS = ('statement', 'holds_when', 'common_mistake')
ORIGINS = ('lesson', 'backfill', 'codex')
REF = ('source_id', 'revision', 'unit_id')


def lesson_turns(store, concept_id=None):
    """Completed lesson turns of a section's own, oldest first: mainline turns that no chapter owns (a chapter recap)."""
    turns = [t for t in store.digest('streams', streaming.brief)
             if t['channel'] == 'mainline' and t['status'] == 'completed' and not t.get('chapter_id')
             and (concept_id is None or t['concept_id'] == concept_id)]
    return sorted(turns, key=lambda t: t['started_at'])


def _text(value, field, limit=MAX_TEXT, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise OperationError('invalid_key_points', f'{field} must be nonempty text of at most {limit} characters')
    return value.strip()


def section_refs(store, concept_id):
    """The source locations a section links to (its links, exercises and notations), which its points may cite."""
    concept = next((c for c in curriculum.model(store)['concepts'] if c['id'] == concept_id), {})
    found = []
    for field in ('links', 'exercises', 'notations'):
        for ref in concept.get(field, []):
            exact = {k: ref[k] for k in REF}
            if exact not in found:
                found.append(exact)
    return found


def _points(store, concept_id, values):
    """Validated points: each {statement, holds_when?, common_mistake?, turn_id?, source_refs?}. A turn_id names the
    section's lesson turn that taught the point; source_refs are locations the section links to."""
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_POINTS:
        raise OperationError('invalid_key_points', f'A section has 1 to {MAX_POINTS} key points')
    taught = {t['id'] for t in lesson_turns(store, concept_id)}
    linked = section_refs(store, concept_id)
    cleaned = []
    for value in values:
        if not isinstance(value, dict):
            raise OperationError('invalid_key_points', 'Each key point is {statement, holds_when, common_mistake, turn_id, source_refs}')
        point: dict = {'statement': _text(value.get('statement'), 'statement', required=True)}
        for field in FIELDS[1:]:
            text = _text(value.get(field) or None, field)
            if text:
                point[field] = text
        if value.get('turn_id') is not None:
            if value['turn_id'] not in taught:
                raise OperationError('invalid_key_points', f"turn_id {value['turn_id']} is not a lesson of this section")
            point['turn_id'] = value['turn_id']
        refs = value.get('source_refs') or []
        if not isinstance(refs, list):
            raise OperationError('invalid_key_points', 'source_refs is a list of {source_id, revision, unit_id}')
        point['source_refs'] = []
        for ref in refs:
            exact = {k: ref.get(k) for k in REF} if isinstance(ref, dict) else None
            if exact not in linked:
                raise OperationError('invalid_key_points', 'A key point cites only source locations its section links to')
            if exact not in point['source_refs']:
                point['source_refs'].append(exact)
        cleaned.append(point)
    if len({p['statement'] for p in cleaned}) < len(cleaned):
        raise OperationError('invalid_key_points', 'Key points repeat a statement')
    return cleaned


def _studied(store, concept_id):
    validate_concept(store, concept_id)
    if not lesson_turns(store, concept_id):
        raise OperationError('not_studied', 'Key points are written for a section with a completed lesson')


def save(store, request):
    """The teacher's points for a section, from the turn that wrote them: a lesson's last step or single reply
    (`lesson`), or the idle job for a section studied before key points existed (`backfill`). They replace the section's
    points and keep the changes the learner asked Codex for, which the teacher was given to keep."""
    concept_id = require_text(request, 'concept_id')
    _studied(store, concept_id)
    turn_id = require_text(request, 'turn_id')
    origin = request.get('origin')
    if origin not in ORIGINS[:2]:
        raise OperationError('invalid_request', 'origin is lesson or backfill')
    old = store.get(POINTS, concept_id) or {}
    if old.get('turn_id') == turn_id:
        return {'key_points': old, 'changed': False}
    value = {'concept_id': concept_id, 'points': _points(store, concept_id, request.get('points')), 'origin': origin,
             'turn_id': turn_id, 'written_at': time.time(), 'requests': old.get('requests', [])}
    return {'key_points': store.put(POINTS, concept_id, value), 'changed': True}


def revise(store, request):
    """Codex changes a section's points because the learner asked: `points` replace them, and `request`, what the
    learner asked for, is kept, so a later lesson that rewrites the points keeps the change unless it contradicts it."""
    concept_id = require_text(request, 'concept_id')
    _studied(store, concept_id)
    asked = _text(request.get('request'), 'request', MAX_REQUEST, required=True)
    old = store.get(POINTS, concept_id) or {}
    value = {'concept_id': concept_id, 'points': _points(store, concept_id, request.get('points')), 'origin': 'codex',
             'written_at': time.time(), 'requests': old.get('requests', []) + [{'text': asked, 'at': time.time()}]}
    return {'key_points': store.put(POINTS, concept_id, value)}


def basis(store, chapter):
    """When each of a chapter's sections got its current points: a chapter sheet written from other points is stale."""
    found = {cid: store.get(POINTS, cid) for cid in chapter['concept_ids']}
    return {cid: value['written_at'] for cid, value in found.items() if value}


def basis_key(value):
    return hashlib.sha1(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def save_sheet(store, request):
    """The paragraph on how a chapter's sections connect, written from the points listed in `basis` (section -> when
    its points were written). A sheet's points are always read live; only the paragraph can fall behind them."""
    chapter_id = require_text(request, 'chapter_id')
    chapter = next((c for c in curriculum.model(store)['chapters'] if c['id'] == chapter_id), None)
    if chapter is None:
        raise OperationError('unknown_chapter', chapter_id)
    written = request.get('basis')
    if not isinstance(written, dict) or len(written) < 2 or not set(written) <= set(chapter['concept_ids']):
        raise OperationError('invalid_request', "basis names two or more of the chapter's sections")
    value = {'chapter_id': chapter_id, 'connection': _text(request.get('connection'), 'connection', MAX_CONNECTION, required=True),
             'basis': written, 'turn_id': require_text(request, 'turn_id'), 'written_at': time.time()}
    return {'sheet': store.put(SHEETS, chapter_id, value)}


def view(store, request):
    """Every section's key points and every chapter sheet, or one section's points (`concept_id`). A sheet is
    `current` while its paragraph was written from the chapter's current points."""
    if request.get('concept_id'):
        concept_id = require_text(request, 'concept_id')
        validate_concept(store, concept_id)
        return {'key_points': store.get(POINTS, concept_id)}
    chapters = {c['id']: c for c in curriculum.model(store)['chapters']}
    sheets = [{**s, 'current': s['basis'] == basis(store, chapters[s['chapter_id']])}
              for s in store.list(SHEETS) if s['chapter_id'] in chapters]
    return {'key_points': store.list(POINTS), 'chapter_sheets': sheets}


def _stale(store, concept_id, value):
    """Whether a section's points sum up a lesson a New lesson replaced (ADR 0023), whose own last step wrote none: the
    new lesson is finished and began after they were written."""
    lessons = [l for l in store.list('lessons') if l['concept_id'] == concept_id]
    if not any(l.get('replaced_by') for l in lessons):
        return False
    current = max((l for l in lessons if not l.get('replaced_by')), key=lambda l: l.get('created_at', 0), default=None)
    return bool(current and all(s.get('turn_id') for s in current['steps']) and current.get('created_at', 0) > value.get('written_at', 0))


def pending(store, request):
    """What the idle job could write: studied sections without points, or whose points sum up a replaced lesson, in
    route order, and chapters whose paragraph is missing or stale, with two or more sections that have points. `exclude`
    leaves out sections still being taught."""
    exclude = set(request.get('exclude') or [])
    taught = {t['concept_id'] for t in lesson_turns(store)}
    model = curriculum.model(store)
    sections = [cid for cid in model['route'] if cid in taught and cid not in exclude
                and (not (value := store.get(POINTS, cid)) or _stale(store, cid, value))]
    chapters = []
    for chapter in model['chapters']:
        written = basis(store, chapter)
        sheet = store.get(SHEETS, chapter['id'])
        if len(written) >= 2 and (not sheet or sheet['basis'] != written):
            chapters.append({'chapter_id': chapter['id'], 'basis': written})
    return {'sections': sections, 'chapters': chapters}


OPERATIONS = {'key_points.save': save, 'key_points.revise': revise, 'key_points.save_sheet': save_sheet,
              'key_points.view': view, 'key_points.pending': pending}
