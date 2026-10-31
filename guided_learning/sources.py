"""Source snapshots preserve exact bytes and extracted text by content revision."""
import hashlib
import io
import os
from pathlib import Path
from .store import OperationError
from .curriculum import source_unit

# Documents that are not text: Codex converts them to PDF and registers the PDF with `converted_from` (ADR 0015).
CONVERTED = {'.doc', '.docx', '.dot', '.dotx', '.odt', '.rtf', '.pages', '.ppt', '.pptx', '.pps', '.ppsx', '.odp', '.key',
             '.xls', '.xlsx', '.ods', '.numbers', '.epub'}

def text_of(data):
    """A text file's content, or None for binary data. UTF-8 (with or without a byte order mark) and UTF-16 with one."""
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = data.decode('utf-16')
    elif b'\x00' in data:
        return None
    else:
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('Text sources must be UTF-8: save the file as UTF-8 and register it again') from None
    return None if '\x00' in text else text

def extract(path, data):
    if path.suffix.lower() == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError('PDF reader unavailable: install the pdf extra (pypdf)') from exc
        reader = PdfReader(io.BytesIO(data))
        units = []
        for n, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ''
                units.append({'id': f'page-{n}', 'locator': {'page': n}, 'text': text, 'status': 'read' if text.strip() else 'needs_review', 'verification': 'pending'})
            except Exception as exc:
                units.append({'id': f'page-{n}', 'locator': {'page': n}, 'text': '', 'status': 'failed', 'error': str(exc), 'verification': 'pending'})
        return units
    if path.suffix.lower() in CONVERTED:
        raise ValueError(f'{path.suffix} files are not read directly: convert to PDF and register the PDF with converted_from')
    text = text_of(data)
    if text is None:
        raise ValueError('Supported sources are PDF or text files: convert other documents to PDF first')
    return [{'id': f'line-{n}', 'locator': {'line': n}, 'text': line} for n, line in enumerate(text.splitlines(), 1)]

def write_snapshot(folder, revision, data):
    """Store the exact bytes under their hash; a crash never leaves a truncated snapshot behind."""
    target = folder / revision
    try:
        if hashlib.sha256(target.read_bytes()).hexdigest() == revision:
            return
    except OSError:
        pass
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f'.{revision}.{os.getpid()}.tmp'
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

def converted_from(raw_path):
    """The document a registered file was converted from, by path and the revision that was converted."""
    if not isinstance(raw_path, str) or not raw_path:
        raise OperationError('invalid_request', 'converted_from must be the path of the original document')
    path = Path(raw_path).resolve()
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise OperationError('invalid_request', f'converted_from must be a readable file: {exc}') from None
    return {'path': str(path), 'revision': hashlib.sha256(data).hexdigest()}

def register(store, request):
    raw_path = request.get('path')
    if not isinstance(raw_path, str) or not raw_path:
        raise OperationError('invalid_request', 'path must be a nonempty string')
    path = Path(raw_path).resolve()
    source_id = 'src-' + hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()[:24]
    previous = store.get('sources', source_id, {})
    original = converted_from(request.get('converted_from')) if 'converted_from' in request else previous.get('converted_from')
    source = {'id': source_id, 'path': str(path), 'revision': previous.get('revision'), 'status': 'failed', 'verification': 'pending', 'errors': [],
              **({'converted_from': original} if original else {})}
    try:
        data = path.read_bytes()
    except OSError as exc:
        source['errors'] = [str(exc)]
        store.put('sources', source_id, source)
        return {'source': source}
    revision = hashlib.sha256(data).hexdigest()
    source['revision'] = revision
    try:
        units = extract(path, data)
        source['status'] = 'read' if units and all(u.get('status', 'read') == 'read' for u in units) else 'needs_review'
        source['errors'] = [u['error'] for u in units if 'error' in u]
    except Exception as exc:
        units = []
        source['errors'] = [str(exc)]
    snapshot = {'source_id': source_id, 'revision': revision, 'path': str(path), 'status': source['status'], 'verification': 'pending', 'units': units, 'errors': source['errors'],
                **({'converted_from': original} if original else {})}
    write_snapshot(store.workspace / 'sources' / source_id, revision, data)
    store.put('source_revisions', source_id + ':' + revision, snapshot)
    store.put('sources', source_id, source)
    return {'source': source}

def read(store, request):
    source_id = request.get('source_id')
    source = store.get('sources', source_id)
    if source is None:
        raise OperationError('unknown_source', str(source_id))
    revision = request.get('revision', source['revision'])
    snapshot = store.get('source_revisions', source_id + ':' + str(revision))
    if snapshot is None:
        raise OperationError('unknown_revision', str(revision))
    return snapshot

def units(store, request):
    """The exact source units behind a list of {source_id, revision, unit_id} references."""
    refs = request.get('refs')
    if not isinstance(refs, list):
        raise OperationError('invalid_request', 'refs must be a list')
    return {'sources': [{**ref, 'unit': source_unit(store, ref)} for ref in refs]}

OPERATIONS = {'source.register': register, 'source.read': read, 'source.units': units}
