"""Course packages (ADR 0020): one `.throughline` file holding a copy of a course and its sources, to give to someone
else or to move or back up one's own. Importing one makes a new course in the library; nothing syncs back."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
import zipfile
from pathlib import Path

from . import images, library, migrations
from .api import execute
from .store import OperationError, Store
from .streaming import PREPARED_STEP

FORMAT = 1
SUFFIX = '.throughline'
LEVELS = ('route', 'lessons', 'everything')
# How a recipient takes a package: as the course it was, or as a fresh start at most at the lessons level, optionally
# with the sender's annotations and side questions to read.
MODES = ('continue', 'fresh', 'fresh-with-notes')

# The lowest share level whose packages carry each namespace. A namespace missing here, such as one an older Throughline
# wrote, is carried only by Everything; a test fails when the code uses a namespace this map leaves out.
NAMESPACES = {
    # The course as built: the route and the sources as they were read.
    'curriculum': 'route', 'sources': 'route', 'source_revisions': 'route', 'page_readings': 'route', 'figures': 'route',
    # What the sender's teacher wrote. Route and lessons carries the lessons and exercises among them (`share`).
    'lessons': 'lessons', 'streams': 'lessons', 'practice_tasks': 'lessons',
    # Frozen prompts hold the sender's course memory, profile and session, so they never leave a course below Everything.
    'stream_snapshots': 'everything',
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
COURSE_KEYS = {'metadata': 'route', 'schema': 'route', 'preferences': 'route', 'widgets': 'route', 'built_for': 'route', 'imported': 'route',
               'position': 'everything', 'profile': 'everything'}

# What a shared lesson step, turn and exercise keep: what the teacher wrote, never the sender's answers or prompts.
STEP_KEYS = ('title', 'added', 'check', 'replied')
TURN_KEYS = ('id', 'concept_id', 'channel', 'prompt', 'language', 'source_refs', 'attempt', 'status', 'text', 'final_text', 'sequence',
             'started_at', 'completed_at', 'title')
TASK_KEYS = ('id', 'concept_id', 'question', 'origin', 'source_refs', 'parts', 'exercise', 'variant_of', 'created_at')
# What the sender's learner profile says about the course; their prior knowledge and notes stay theirs.
BUILT_FOR = ('goal', 'depth', 'focus')

_SEGMENT = r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}'
# The only entries a package may hold. Anything else, a path out of the course folder included, refuses the package.
ENTRY = re.compile(rf'(?:manifest\.json|course\.sqlite3|sources/{_SEGMENT}/[0-9a-f]{{64}}|{images.FOLDER}/{images.NAME.pattern})')
MAX_UNPACKED = 8 << 30
MAX_RATIO = 50  # unpacked bytes per packed byte, well beyond what databases and text compress to
MAX_MANIFEST = 1 << 20


def share(rows, level, notes=False):
    """The records a course carries at a share level, from its (namespace, key, value) rows, values as JSON text. With
    `notes`, the sender's learner annotations and answered side questions come too, marked as theirs (`from_sender`)."""
    if level == 'everything':
        yield from rows
        return
    rank = LEVELS.index(level)
    kept, profile = {}, None
    for namespace, key, value in rows:
        if (namespace, key) == ('course', 'profile'):
            profile = json.loads(value)
        own = COURSE_KEYS.get(key, 'everything') if namespace == 'course' else NAMESPACES.get(namespace, 'everything')
        if LEVELS.index(own) <= rank or notes and namespace in ('annotations', 'web_branches'):
            kept.setdefault(namespace, {})[key] = json.loads(value)
    streams, lessons, tasks = kept.pop('streams', {}), kept.pop('lessons', {}), kept.pop('practice_tasks', {})
    shared = {'streams': {}, 'lessons': {}, 'practice_tasks': {}}
    if level == 'lessons':
        for lesson in lessons.values():
            steps, written = _steps(lesson, streams)
            if written:
                shared['lessons'][lesson['id']] = {**{k: lesson[k] for k in ('id', 'concept_id', 'request', 'created_at', 'outline') if k in lesson}, 'steps': steps}
                for turn in written:
                    shared['streams'][turn['id']] = _turn(turn, channel=PREPARED_STEP)
        for key, task in tasks.items():
            if task.get('origin') in ('source', 'self_created') and not task.get('chapter_id') and task.get('status') != 'replaced':
                shared['practice_tasks'][key] = {**{k: task[k] for k in TASK_KEYS if k in task}, 'status': 'pending', 'history': []}
        for task in shared['practice_tasks'].values():
            if task.get('variant_of') not in shared['practice_tasks']:
                task.pop('variant_of', None)
    if notes:
        branches = {}
        for key, branch in kept.pop('web_branches', {}).items():
            turns = [streams.get(t) for t in [branch.get('turn_id')] + [r.get('turn_id') for r in branch.get('replies', [])]]
            if turns[0] and turns[0]['status'] == 'completed':
                answered = [r for r, t in zip(branch.get('replies', []), turns[1:]) if t and t['status'] == 'completed']
                branches[key] = {**{k: v for k, v in branch.items() if not k.startswith('supplement')}, 'replies': answered,
                                 'status': 'answered', 'from_sender': True}
                for turn in [turns[0]] + [streams[r['turn_id']] for r in answered]:
                    shared['streams'][turn['id']] = _turn(turn)
        shared['web_branches'] = branches
        known = shared['streams'].keys() | shared['practice_tasks'].keys()
        shared['annotations'] = {key: {**note, 'from_sender': True} for key, note in kept.pop('annotations', {}).items()
                                 if all(note.get(field) in known for field in ('turn_id', 'task_id') if note.get(field))}
    course = kept.setdefault('course', {})
    if profile and not course.get('built_for'):
        built = {k: profile[k] for k in BUILT_FOR if profile.get(k)}
        if built:
            course['built_for'] = built
    for namespace, records in {**kept, **shared}.items():
        for key, value in records.items():
            yield namespace, key, json.dumps(value, ensure_ascii=False)


def _steps(lesson, streams):
    """A lesson's steps as shared: each step written to its end keeps its text as a hidden turn (`written`) that the
    recipient's Start or Continue reveals, and the plan after the last such step stays a plan."""
    steps, written = [], []
    for step in lesson.get('steps', []):
        turn = streams.get(step.get('turn_id'))
        if turn and turn['status'] == 'completed' and turn['channel'] == 'mainline' and len(written) == len(steps):
            steps.append({**{k: step[k] for k in STEP_KEYS if k in step}, 'written': turn['id']})
            written.append(turn)
        else:
            steps.append({'title': step['title'], 'added': step.get('added', False)})
    return steps, written


def _turn(turn, channel=None):
    return {**{k: turn[k] for k in TURN_KEYS if k in turn}, 'channel': channel or turn['channel'], 'record_user': False,
            'metrics': {}, 'attempts': [], 'resume_requests': []}


def contents(rows):
    """What a course's records hold, as the export shows it and the manifest records it."""
    counts = {'lessons': 0, 'exercises': 0, 'notes': 0, 'questions': 0, 'evidence': 0}
    field = {'lessons': 'lessons', 'practice_tasks': 'exercises', 'annotations': 'notes', 'web_branches': 'questions', 'evidence': 'evidence'}
    for namespace, _, _ in rows:
        if namespace in field:
            counts[field[namespace]] += 1
    return counts


def summary(workspace):
    """What each share level of a course would hold, for the export to show before writing anything."""
    workspace = Path(workspace).resolve()
    execute(workspace, {'op': 'course.status'})  # migrates first, as an export does
    rows = list(_rows(workspace / 'course.sqlite3'))
    return {level: contents(list(share(iter(rows), level))) for level in LEVELS}


def export(workspace, destination, level='everything'):
    """Write a course at a share level to `destination`; the course may be open meanwhile."""
    from .commands import version
    if level not in LEVELS:
        raise OperationError('invalid_request', 'level must be route, lessons or everything')
    workspace = Path(workspace).resolve()
    status = execute(workspace, {'op': 'course.status'})  # migrates the course first, so the package is current
    destination = Path(destination).resolve()
    partial = destination.with_name('.' + destination.name + '.partial')
    copy = destination.with_name('.' + destination.name + '.sqlite3')
    shared = destination.with_name('.' + destination.name + '.shared.sqlite3')
    folders = ('sources', images.FOLDER) if level == 'everything' else ('sources',)  # images belong to answers and notes
    files = sorted(path for folder in folders for path in (workspace / folder).rglob('*')
                   if path.is_file() and ENTRY.fullmatch(path.relative_to(workspace).as_posix()))
    try:
        for path in (copy, shared):
            path.unlink(missing_ok=True)
        live = sqlite3.connect(workspace / 'course.sqlite3', timeout=30)
        try:
            live.execute('VACUUM INTO ?', (str(copy),))  # one consistent, compacted file, taken beside writers
        finally:
            live.close()
        if level != 'everything':
            _write(shared, share(_rows(copy), level))
            os.replace(shared, copy)
        rows = list(_rows(copy))
        course = {key: json.loads(value) for namespace, key, value in rows if namespace == 'course'}
        manifest = {'format': FORMAT, 'level': level, 'schema': (course.get('schema') or {}).get('version', 1),
                    'throughline': version(), 'name': workspace.name, 'title': status['course']['title'],
                    'language': (course.get('preferences') or {}).get('language'), 'contents': contents(rows),
                    **({'built_for': course['built_for']} if course.get('built_for') else {}),
                    'sources': [{'id': s['id'], 'revision': s['revision'], 'name': Path(s['path']).name} for s in status['sources']]}
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=1))
            archive.write(copy, 'course.sqlite3')
            for path in files:
                archive.write(path, path.relative_to(workspace).as_posix())
        os.replace(partial, destination)
    finally:
        for path in (partial, copy, shared):
            path.unlink(missing_ok=True)
    return {'path': str(destination), 'size': destination.stat().st_size, 'level': level, 'title': manifest['title'],
            'sources': len(manifest['sources']), 'contents': manifest['contents']}


def inspect(package):
    """A package's manifest, checked as an import checks it, for choosing how to import it."""
    with _open(package) as archive:
        manifest = _manifest(Path(package), archive, archive.infolist())
    return {**{k: manifest.get(k) for k in ('level', 'title', 'name', 'language', 'contents', 'built_for')},
            'sources': len(manifest.get('sources') or []), 'modes': list(MODES if manifest['level'] == 'everything' else MODES[1:2])}


def import_package(package, root, name=None, mode=None):
    """Make a new course in the library at `root` from a package. `continue` (an Everything package's default) takes
    the course as it was; `fresh` (the default otherwise) starts over at most at the lessons level, and
    `fresh-with-notes` also keeps the sender's notes and questions to read. The package is untrusted: only known entries
    are unpacked, and its records are copied into a database made here."""
    package, root = Path(package), Path(root).resolve()
    with _open(package) as archive:
        entries = archive.infolist()
        manifest = _manifest(package, archive, entries)
        mode = mode or ('continue' if manifest['level'] == 'everything' else 'fresh')
        if mode not in MODES:
            raise OperationError('invalid_request', 'mode must be continue, fresh or fresh-with-notes')
        if mode != 'fresh' and manifest['level'] != 'everything':
            raise OperationError('invalid_request', 'Only a package of the whole course can be continued or keep its notes')
        target = _target(root, name, manifest.get('name'))
        staging = root / '.throughline' / 'imports' / uuid.uuid4().hex
        course = staging / 'course'
        try:
            course.mkdir(parents=True)
            archive_db = staging / 'package.sqlite3'
            with archive.open('course.sqlite3') as source, archive_db.open('wb') as out:
                shutil.copyfileobj(source, out)
            level = manifest['level'] if mode == 'continue' else LEVELS[min(LEVELS.index(manifest['level']), LEVELS.index('lessons'))]
            _copy_records(archive_db, course, level, mode, manifest)
            for entry in entries:
                if entry.filename.startswith('sources/') or mode != 'fresh' and entry.filename.startswith(images.FOLDER + '/'):
                    _unpack(archive, entry, course / entry.filename)
            result = execute(course, {'op': 'course.status'})  # migrates an older course and proves it opens
            if target.exists():
                raise OperationError('course_exists', f'A course named {target.name} already exists')
            os.replace(course, target)
        except (zipfile.BadZipFile, EOFError, OSError) as exc:  # a damaged package, or a disk that filled up
            raise OperationError('invalid_package', f'The package could not be unpacked: {exc}') from None
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    return {'name': target.name, 'path': str(target), 'title': result['course']['title'], 'level': manifest['level'], 'mode': mode,
            'sources': len(result['sources'])}


def _open(package):
    try:
        return zipfile.ZipFile(package)
    except (zipfile.BadZipFile, OSError) as exc:
        raise OperationError('invalid_package', f'Not a Throughline course package: {exc}') from None


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
    if manifest['format'] > FORMAT or manifest.get('level') not in LEVELS:
        raise OperationError('package_too_new', 'This package was made by a newer version of Throughline; update Throughline to import it')
    if manifest['schema'] > migrations.VERSION:
        raise OperationError('course_too_new', f"This course was saved by a newer version of Throughline (format {manifest['schema']}); update Throughline to open it")
    return manifest


def suggested_name(root, suggested):
    """The name an import gives a course when none is asked for: the package's, made unique in the library."""
    base = suggested if isinstance(suggested, str) and library.NAME.match(suggested) else 'imported-course'
    for number in range(1, 1000):
        candidate = base if number == 1 else f'{base[:60]}-{number}'
        if not (Path(root) / candidate).exists():
            return candidate
    raise OperationError('course_exists', f'Courses named {base} already exist; choose a name')


def _target(root, name, suggested):
    """The new course's folder: the name asked for, which must be free, or the package's name made unique."""
    target = library.course_path(root, suggested_name(root, suggested) if name is None else name)
    if target.exists():
        raise OperationError('course_exists', f'A course named {target.name} already exists')
    return target


def _rows(database):
    """A course database's records, read only as data: a crafted file is never opened as a course."""
    try:
        db = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    except sqlite3.Error as exc:
        raise OperationError('invalid_package', f'The package database is unreadable: {exc}') from None
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute("SELECT type FROM sqlite_master WHERE name='documents'").fetchone() != ('table',):
            raise OperationError('invalid_package', 'The package database holds no course')
        for namespace, key, value in db.execute('SELECT namespace, key, value FROM documents'):
            if not all(isinstance(field, str) for field in (namespace, key, value)):
                raise OperationError('invalid_package', 'The package database holds a malformed record')
            json.loads(value)
            yield namespace, key, value
    except sqlite3.Error as exc:  # not a database at all
        raise OperationError('invalid_package', f'The package database is unreadable: {exc}') from None
    except ValueError as exc:  # a record that is not JSON
        raise OperationError('invalid_package', f'The package database holds a malformed record: {exc}') from None
    finally:
        db.close()


def _write(database, rows):
    db = sqlite3.connect(database)
    try:
        with db:
            db.execute('CREATE TABLE documents (namespace TEXT, key TEXT, value TEXT NOT NULL, PRIMARY KEY(namespace, key))')
            db.executemany('INSERT INTO documents VALUES (?, ?, ?)', rows)
    finally:
        db.close()


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


def _copy_records(package_db, course, level, mode, manifest):
    """Copy the package's records, as the import takes them, into a new course database. A fresh start is marked as
    imported, which Studio warns about under Full access."""
    store = Store(course, create=True)
    # A package already holds only its level's records; sharing applies only when the recipient takes less.
    take = 'everything' if level == manifest['level'] else level
    try:
        with store.db:
            store.db.executemany('INSERT INTO documents VALUES (?, ?, ?)', share(_rows(package_db), take, notes=mode == 'fresh-with-notes'))
            metadata = store.get('course', 'metadata')
            if not isinstance(metadata, dict) or not isinstance(metadata.get('title'), str):
                raise OperationError('invalid_package', 'The package database holds no course')
            store.put('course', 'metadata', {**metadata, 'id': str(uuid.uuid4())})
            if mode != 'continue':
                store.put('course', 'imported', {'title': manifest.get('title'), 'level': level, 'notes': mode == 'fresh-with-notes', 'at': time.time()})
    except sqlite3.IntegrityError as exc:  # a key twice
        raise OperationError('invalid_package', f'The package database holds a malformed record: {exc}') from None
    finally:
        store.db.close()
