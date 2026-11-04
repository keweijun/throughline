"""Page readings (ADR 0019): Codex reads each page of a PDF source as an image and records its text, its figures and what it
could not read. A page with a reading is verified, and its reading stands in for the extracted text wherever a page's text
is used, except search and highlight positions, which keep the extraction in the snapshot.

Each page's reading is its own record, so readings saved at the same time (Codex's subagents reading parts of a source)
never overwrite one another. Figures are also indexed by a short id, which a lesson's `figure` fence names; the id
belongs to one revision, page and position on the page, so the crop it draws never changes.
"""
import hashlib
import os
import threading
import time
from pathlib import Path
from . import pages
from .store import OperationError

READINGS = 'page_readings'
FIGURES = 'figures'
RENDERS = 'page_images'  # the course folder where rendered pages and crops are written
MAX_PAGES = 100  # pages in one save or render request, a sanity limit
MAX_FIGURES = 30  # figures on one page, a sanity limit


def key(source_id, revision, page):
    return f'{source_id}:{revision}:{page:06d}'


def figure_id(source_id, revision, page, index):
    return 'fig-' + hashlib.sha256(f'{source_id}:{revision}:{page}:{index}'.encode()).hexdigest()[:10]


def _snapshot(store, request):
    """The source and revision a request names (its current revision by default), which must be a PDF."""
    source_id = request.get('source_id')
    source = store.get('sources', source_id) if isinstance(source_id, str) else None
    if source is None:
        raise OperationError('unknown_source', str(source_id))
    revision = request.get('revision', source['revision'])
    snapshot = store.shared('source_revisions', f'{source_id}:{revision}')
    if snapshot is None:
        raise OperationError('unknown_revision', str(revision))
    if Path(snapshot['path']).suffix.lower() != '.pdf':
        raise OperationError('invalid_request', 'Only PDF sources are read as pages; a text source is already exact')
    return source_id, revision, sum(1 for u in snapshot['units'] if 'page' in u.get('locator', {}))


def _text(value, field, required=False):
    if value is None and not required:
        return ''
    if not isinstance(value, str) or (required and not value.strip()):
        raise OperationError('invalid_reading', f'{field} must be {"a nonempty" if required else "a"} string')
    return value.strip()


def _figures(raw, page):
    if not isinstance(raw, list) or len(raw) > MAX_FIGURES:
        raise OperationError('invalid_reading', f'figures on page {page} must be a list of at most {MAX_FIGURES}')
    figures = []
    for item in raw:
        if not isinstance(item, dict):
            raise OperationError('invalid_reading', f'each figure on page {page} must be an object')
        if not pages.valid_box(item.get('box')):
            raise OperationError('invalid_reading', f'a figure on page {page} needs box [left, top, right, bottom], fractions of the page from its top left')
        figures.append({'label': _text(item.get('label'), 'label'), 'caption': _text(item.get('caption'), 'caption'),
                        'description': _text(item.get('description'), 'description', required=True), 'box': [float(v) for v in item['box']]})
    return figures


def save(store, request):
    """Store readings of pages of one revision. Saving a page again replaces its reading and its figures."""
    source_id, revision, count = _snapshot(store, request)
    readings = request.get('readings')
    if not isinstance(readings, list) or not 1 <= len(readings) <= MAX_PAGES:
        raise OperationError('invalid_request', f'readings must list 1 to {MAX_PAGES} pages')
    checked = {}
    for reading in readings:
        page = reading.get('page') if isinstance(reading, dict) else None
        if not isinstance(page, int) or isinstance(page, bool) or not 1 <= page <= count:
            raise OperationError('invalid_reading', f'page must be a page number from 1 to {count}')
        if page in checked:
            raise OperationError('invalid_reading', f'page {page} is given twice')
        problems = reading.get('problems', [])
        if not isinstance(problems, list) or any(not isinstance(p, str) or not p.strip() for p in problems):
            raise OperationError('invalid_reading', f'problems on page {page} must be a list of nonempty strings')
        checked[page] = {'source_id': source_id, 'revision': revision, 'page': page, 'text': _text(reading.get('text'), 'text'),
                         'figures': _figures(reading.get('figures', []), page), 'problems': [p.strip() for p in problems]}
    now = time.time()
    for page, reading in checked.items():
        for old in (store.get(READINGS, key(source_id, revision, page)) or {}).get('figures', []):
            store.delete(FIGURES, old['id'])
        for index, figure in enumerate(reading['figures'], 1):
            figure['id'] = figure_id(source_id, revision, page, index)
            store.put(FIGURES, figure['id'], {**figure, 'source_id': source_id, 'revision': revision, 'page': page, 'index': index})
        store.put(READINGS, key(source_id, revision, page), {**reading, 'read_at': now})
    return {'saved': sorted(checked), 'readings': summary(store, source_id, revision, count)}


def _brief(reading):
    return {'source_id': reading['source_id'], 'revision': reading['revision'], 'page': reading['page'], 'problems': bool(reading['problems'])}


def read_pages(store):
    """{(source_id, revision): {page: has problems}} for every reading in the course."""
    found = {}
    for reading in store.digest(READINGS, _brief):
        found.setdefault((reading['source_id'], reading['revision']), {})[reading['page']] = reading['problems']
    return found


def _ranges(numbers):
    spans = []
    for n in sorted(numbers):
        if spans and spans[-1][1] == n - 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return spans


def summary(store, source_id, revision, count, read=None):
    """How much of a revision is read: page count, pages read, and the unread pages and pages with problems as [first, last] ranges."""
    done = (read_pages(store) if read is None else read).get((source_id, revision), {})
    return {'pages': count, 'read': len(done), 'unread': _ranges(set(range(1, count + 1)) - set(done)),
            'problems': _ranges(page for page, problems in done.items() if problems)}


def overlay(unit, reading):
    """A source unit as the teacher reads it: the page's reading in place of its extracted text, when there is one."""
    if not reading:
        return unit
    shown = {**unit, 'text': reading['text'], 'status': 'read', 'verification': 'verified', 'reading': True}
    if reading['figures']:
        shown['figures'] = [{k: f[k] for k in ('id', 'label', 'caption', 'description') if f[k]} for f in reading['figures']]
    if reading['problems']:
        shown['problems'] = list(reading['problems'])
    return shown


def unit_reading(store, source_id, revision, unit):
    page = unit.get('locator', {}).get('page')
    return store.shared(READINGS, key(source_id, revision, page)) if isinstance(page, int) else None


def source_view(store, snapshot):
    """A snapshot as `source.read` returns it: units overlaid with their readings and, for a PDF, what is read."""
    if Path(snapshot['path']).suffix.lower() != '.pdf':
        return snapshot
    source_id, revision = snapshot['source_id'], snapshot['revision']
    found = {r['page']: r for r in store.matching(READINGS, 'source_id', source_id) if r['revision'] == revision}
    snapshot['units'] = [overlay(u, found.get(u.get('locator', {}).get('page'))) for u in snapshot['units']]
    count = sum(1 for u in snapshot['units'] if 'page' in u.get('locator', {}))
    snapshot['readings'] = summary(store, source_id, revision, count, {(source_id, revision): {p: bool(r['problems']) for p, r in found.items()}})
    if count and snapshot['readings']['read'] == count:
        snapshot['verification'] = 'verified'
    return snapshot


def annotate(store, sources):
    """Registered sources with how much of their current revision is read: `pages`, `pages_read` and `problem_pages`."""
    read = read_pages(store)
    for source in sources:
        snapshot = store.shared('source_revisions', f"{source['id']}:{source.get('revision')}") if source.get('revision') else None
        if snapshot is None or Path(snapshot['path']).suffix.lower() != '.pdf':
            continue
        done = read.get((source['id'], source['revision']), {})
        source.update(pages=sum(1 for u in snapshot['units'] if 'page' in u.get('locator', {})), pages_read=len(done),
                      problem_pages=sum(1 for problems in done.values() if problems))
        if source['pages'] and source['pages_read'] == source['pages']:
            source['verification'] = 'verified'
    return sources


def figure(store, request):
    """A figure by id: where it is (source, revision, page and box) and its label, caption and description."""
    found = store.get(FIGURES, request.get('id')) if isinstance(request.get('id'), str) else None
    if found is None:
        raise OperationError('unknown_figure', f'Unknown figure: {request.get("id")}')
    return {'figure': {**found, 'unit_id': f"page-{found['page']}"}}


_VERIFIED = {}
_VERIFY_LOCK = threading.Lock()


def verified_snapshot(path, revision):
    """Whether a snapshot's bytes still hash to its revision. Hashed in chunks so a large PDF never sits in memory, and
    once per version of the file: a reader fetches a large PDF range by range and would otherwise rehash it each time."""
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns, stat.st_ino)
    with _VERIFY_LOCK:
        if key not in _VERIFIED:
            digest = hashlib.sha256()
            with path.open('rb') as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b''):
                    digest.update(chunk)
            _VERIFIED[key] = digest.hexdigest() == revision
        return _VERIFIED[key]


def snapshot_path(workspace, source_id, revision):
    """The stored snapshot of a source revision, checked against its revision."""
    root = (Path(workspace) / 'sources').resolve()
    path = (root / source_id / revision).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise OperationError('unavailable_source', 'Source snapshot unavailable')
    if not verified_snapshot(path, revision):
        raise OperationError('unavailable_source', 'Source snapshot integrity check failed')
    return path


def render(store, request):
    """Draw pages, a box on a page, or figures by id as PNG files Codex can look at, each about `size` pixels on its long
    side. `out` is the folder to write to, by default `page_images` in the course."""
    size = request.get('size', pages.SIZE)
    if not isinstance(size, int) or isinstance(size, bool) or not pages.MIN_SIZE <= size <= pages.MAX_SIZE:
        raise OperationError('invalid_request', f'size must be a number of pixels from {pages.MIN_SIZE} to {pages.MAX_SIZE}')
    if 'figures' in request:
        ids = request['figures']
        if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_PAGES:
            raise OperationError('invalid_request', f'figures must list 1 to {MAX_PAGES} figure ids')
        wanted = [figure(store, {'id': i})['figure'] for i in ids]
        targets = [(f['source_id'], f['revision'], f['page'], f['box'], f['id']) for f in wanted]
    else:
        source_id, revision, count = _snapshot(store, request)
        numbers = request.get('pages', [request['page']] if 'page' in request else None)
        if not isinstance(numbers, list) or not 1 <= len(numbers) <= MAX_PAGES or any(not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= count for n in numbers):
            raise OperationError('invalid_request', f'pages must list 1 to {MAX_PAGES} page numbers from 1 to {count}')
        box = request.get('box')
        if box is not None and not pages.valid_box(box):
            raise OperationError('invalid_request', 'box must be [left, top, right, bottom], fractions of the page from its top left')
        targets = [(source_id, revision, n, box, None) for n in numbers]
    folder = Path(request['out']).resolve() if isinstance(request.get('out'), str) and request['out'] else store.workspace / RENDERS
    folder.mkdir(parents=True, exist_ok=True)
    snapshots, images = {}, []
    for source_id, revision, page, box, fid in targets:
        if (source_id, revision) not in snapshots:
            snapshots[source_id, revision] = snapshot_path(store.workspace, source_id, revision)
        part = fid or ('box-' + hashlib.sha256(repr(box).encode()).hexdigest()[:8] if box else 'page')
        path = folder / f'{source_id}-{revision[:12]}-p{page:04d}-{part}-{size}.png'
        if not path.is_file():
            partial = path.with_name(f'.{path.name}.{os.getpid()}.partial')
            partial.write_bytes(pages.render(snapshots[source_id, revision], page, box, size))
            partial.replace(path)
        images.append({'source_id': source_id, 'revision': revision, 'page': page, **({'figure': fid} if fid else {}), 'path': str(path)})
    return {'images': images}


OPERATIONS = {'source.readings.save': save, 'source.figure': figure, 'source.render': render}
