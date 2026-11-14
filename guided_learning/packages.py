"""Course packages (ADR 0020): one `.throughline` file holding a copy of a course and its sources, to give to someone
else or to move or back up one's own. Importing one makes a new course in the library; nothing syncs back."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
import zipfile
from pathlib import Path

from . import images, library, migrations
from .api import execute
from .store import OperationError, Store

FORMAT = 1
SUFFIX = '.throughline'
LEVELS = ('route', 'lessons', 'everything')

# The lowest share level whose packages carry each namespace. A namespace missing here, such as one an older Throughline
# wrote, is carried only by Everything; a test fails when the code uses a namespace this map leaves out.
NAMESPACES = {
    # The course as built: the route and the sources as they were read.
    'curriculum': 'route', 'sources': 'route', 'source_revisions': 'route', 'page_readings': 'route', 'figures': 'route',
    # What the sender's teacher wrote. Route and lessons carries the lessons and exercises among them, without the
    # sender's answers or the frozen prompts.
    'lessons': 'lessons', 'streams': 'lessons', 'stream_snapshots': 'lessons', 'practice_tasks': 'lessons',
    # The sender's own learning, and the work queued for it.
    'interactions': 'everything', 'evidence': 'everything', 'evidence_deferred': 'everything', 'evidence_resolutions': 'everything',
    'sidequestions': 'everything', 'web_branches': 'everything', 'teaching': 'everything', 'deferred_explanations': 'everything',
    'checkpoint_receipts': 'everything', 'memory': 'everything', 'memory_notes': 'everything', 'memory_requests': 'everything',
    'memory_consolidations': 'everything', 'derived_notes': 'everything', 'annotations': 'everything', 'review_sets': 'everything',
    'review_postponements': 'everything', 'review_warm_ups': 'everything', 'course_change': 'everything',
    'practice_jobs': 'everything', 'preparation_jobs': 'everything', 'preparation_payloads': 'everything',
    'chapter_builds': 'everything', 'background_jobs': 'everything', 'background_receipts': 'everything',
}
# The course namespace holds both kinds, so its keys are classified one by one.
COURSE_KEYS = {'metadata': 'route', 'schema': 'route', 'preferences': 'route', 'widgets': 'route',
               'position': 'everything', 'profile': 'everything'}

_SEGMENT = r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}'
# The only entries a package may hold. Anything else, a path out of the course folder included, refuses the package.
ENTRY = re.compile(rf'(?:manifest\.json|course\.sqlite3|sources/{_SEGMENT}/[0-9a-f]{{64}}|{images.FOLDER}/{images.NAME.pattern})')
MAX_UNPACKED = 8 << 30
MAX_RATIO = 50  # unpacked bytes per packed byte, well beyond what databases and text compress to
MAX_MANIFEST = 1 << 20


def export(workspace, destination):
    """Write the whole course (the Everything level) to `destination`; the course may be open meanwhile."""
    from .commands import version
    workspace = Path(workspace).resolve()
    status = execute(workspace, {'op': 'course.status'})  # migrates the course first, so the package is current
    destination = Path(destination).resolve()
    partial = destination.with_name('.' + destination.name + '.partial')
    copy = destination.with_name('.' + destination.name + '.sqlite3')
    files = sorted(path for folder in ('sources', images.FOLDER) for path in (workspace / folder).rglob('*')
                   if path.is_file() and ENTRY.fullmatch(path.relative_to(workspace).as_posix()))
    try:
        copy.unlink(missing_ok=True)
        live = sqlite3.connect(workspace / 'course.sqlite3', timeout=30)
        try:
            live.execute('VACUUM INTO ?', (str(copy),))  # one consistent, compacted file, taken beside writers
        finally:
            live.close()
        manifest = {'format': FORMAT, 'level': 'everything', 'schema': _record(copy, 'course', 'schema').get('version', 1),
                    'throughline': version(), 'name': workspace.name, 'title': status['course']['title'],
                    'language': _record(copy, 'course', 'preferences').get('language'),
                    'sources': [{'id': s['id'], 'revision': s['revision'], 'name': Path(s['path']).name} for s in status['sources']]}
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=1))
            archive.write(copy, 'course.sqlite3')
            for path in files:
                archive.write(path, path.relative_to(workspace).as_posix())
        os.replace(partial, destination)
    finally:
        partial.unlink(missing_ok=True)
        copy.unlink(missing_ok=True)
    return {'path': str(destination), 'size': destination.stat().st_size, 'level': 'everything', 'title': manifest['title'],
            'sources': len(manifest['sources'])}


def import_package(package, root, name=None):
    """Make a new course in the library at `root` from a package, continuing where its sender left off. The package
    is untrusted: only known entries are unpacked, and its records are copied into a database made here."""
    package, root = Path(package), Path(root).resolve()
    try:
        archive = zipfile.ZipFile(package)
    except (zipfile.BadZipFile, OSError) as exc:
        raise OperationError('invalid_package', f'Not a Throughline course package: {exc}') from None
    with archive:
        entries = archive.infolist()
        manifest = _manifest(package, archive, entries)
        target = _target(root, name, manifest.get('name'))
        staging = root / '.throughline' / 'imports' / uuid.uuid4().hex
        course = staging / 'course'
        try:
            course.mkdir(parents=True)
            archive_db = staging / 'package.sqlite3'
            with archive.open('course.sqlite3') as source, archive_db.open('wb') as out:
                shutil.copyfileobj(source, out)
            _copy_records(archive_db, course)
            for entry in entries:
                if entry.filename.startswith(('sources/', images.FOLDER + '/')):
                    _unpack(archive, entry, course / entry.filename)
            result = execute(course, {'op': 'course.status'})  # migrates an older course and proves it opens
            if target.exists():
                raise OperationError('course_exists', f'A course named {target.name} already exists')
            os.replace(course, target)
        except (zipfile.BadZipFile, EOFError, OSError) as exc:  # a damaged package, or a disk that filled up
            raise OperationError('invalid_package', f'The package could not be unpacked: {exc}') from None
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    return {'name': target.name, 'path': str(target), 'title': result['course']['title'], 'level': manifest['level'],
            'sources': len(result['sources'])}


def _manifest(package, archive, entries):
    names = [entry.filename for entry in entries]
    unexpected = next((n for n in names if not ENTRY.fullmatch(n)), None)
    if unexpected is not None:
        raise OperationError('invalid_package', f'The package holds an unexpected entry: {unexpected}')
    if len(set(names)) != len(names) or 'manifest.json' not in names or 'course.sqlite3' not in names:
        raise OperationError('invalid_package', 'The package is incomplete or holds an entry twice')
    unpacked = sum(entry.file_size for entry in entries)
    if unpacked > MAX_UNPACKED or unpacked > MAX_RATIO * max(package.stat().st_size, 1 << 20):
        raise OperationError('invalid_package', 'The package would unpack far beyond its size')
    if archive.getinfo('manifest.json').file_size > MAX_MANIFEST:
        raise OperationError('invalid_package', 'The package manifest is too large')
    try:
        manifest = json.loads(archive.read('manifest.json'))
    except ValueError:
        manifest = None
    if not isinstance(manifest, dict) or not isinstance(manifest.get('format'), int) or not isinstance(manifest.get('schema'), int):
        raise OperationError('invalid_package', 'The package manifest is unreadable')
    if manifest['format'] > FORMAT or manifest.get('level') != 'everything':
        raise OperationError('package_too_new', 'This package was made by a newer version of Throughline; update Throughline to import it')
    if manifest['schema'] > migrations.VERSION:
        raise OperationError('course_too_new', f"This course was saved by a newer version of Throughline (format {manifest['schema']}); update Throughline to open it")
    return manifest


def _target(root, name, suggested):
    """The new course's folder: the name asked for, which must be free, or the package's name made unique."""
    if name is not None:
        target = library.course_path(root, name)
        if target.exists():
            raise OperationError('course_exists', f'A course named {name} already exists')
        return target
    base = suggested if isinstance(suggested, str) and library.NAME.match(suggested) else 'imported-course'
    for number in range(1, 1000):
        candidate = base if number == 1 else f'{base[:60]}-{number}'
        if not (root / candidate).exists():
            return library.course_path(root, candidate)
    raise OperationError('course_exists', f'Courses named {base} already exist; choose a name')


def _copy_records(package_db, course):
    """Copy the package's records into a new course database, reading the package's file only as data."""
    try:
        incoming = sqlite3.connect(package_db.resolve().as_uri() + '?mode=ro', uri=True)
    except sqlite3.Error as exc:
        raise OperationError('invalid_package', f'The package database is unreadable: {exc}') from None
    store = Store(course, create=True)
    try:
        incoming.execute('PRAGMA trusted_schema=OFF')
        if incoming.execute("SELECT type FROM sqlite_master WHERE name='documents'").fetchone() != ('table',):
            raise OperationError('invalid_package', 'The package database holds no course')
        with store.db:
            for namespace, key, value in incoming.execute('SELECT namespace, key, value FROM documents'):
                if not all(isinstance(field, str) for field in (namespace, key, value)):
                    raise OperationError('invalid_package', 'The package database holds a malformed record')
                json.loads(value)
                store.db.execute('INSERT INTO documents VALUES (?, ?, ?)', (namespace, key, value))
            metadata = store.get('course', 'metadata')
            if not isinstance(metadata, dict) or not isinstance(metadata.get('title'), str):
                raise OperationError('invalid_package', 'The package database holds no course')
            store.put('course', 'metadata', {**metadata, 'id': str(uuid.uuid4())})
    except OperationError:
        raise
    except (sqlite3.Error, ValueError) as exc:  # not a database, or a record that is not JSON
        raise OperationError('invalid_package', f'The package database is unreadable: {exc}') from None
    finally:
        incoming.close()
        store.db.close()


def _unpack(archive, entry, path):
    """Write one source or image file, refusing one whose bytes do not match the hash that names it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with archive.open(entry) as source, path.open('wb') as out:
        while chunk := source.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    if not path.name.startswith(digest.hexdigest()):
        raise OperationError('invalid_package', f'{entry.filename} does not match its content')


def _record(database, namespace, key):
    db = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        row = db.execute('SELECT value FROM documents WHERE namespace=? AND key=?', (namespace, key)).fetchone()
    finally:
        db.close()
    return json.loads(row[0]) if row else {}
