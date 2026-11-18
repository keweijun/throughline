"""The course library: the learner's Throughline folder, holding every course workspace."""
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

from .api import execute
from .store import OperationError

log = logging.getLogger(__name__)
NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')


def default_root():
    """~/Throughline: easy to find, and outside Documents, which OneDrive or iCloud often sync. Synced SQLite courses can corrupt."""
    if os.environ.get('GUIDED_LEARNING_HOME'):
        return Path(os.environ['GUIDED_LEARNING_HOME'])
    return Path.home() / 'Throughline'


def legacy_roots():
    """Where earlier versions kept courses by default; setup moves them into the current library."""
    if os.environ.get('GUIDED_LEARNING_HOME'):
        return []
    roots = [Path.home() / 'Documents' / 'Throughline']
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        roots.append(Path(os.environ['LOCALAPPDATA']) / 'guided-learning' / 'courses')
    roots.append(Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'guided-learning' / 'courses')
    return roots


def state_dir():
    """Host bookkeeping, kept out of sight inside the library."""
    return default_root() / '.throughline'


def host_key():
    """The secret a browser or command shows to use the host, so other people's programs on a shared computer can't.

    Kept across launches, so a tab left open keeps working when the host restarts on the same port (an update), and
    readable only by this user: the program that reads it could read the courses anyway."""
    path = state_dir() / 'host-key'
    try:
        key = path.read_text(encoding='ascii').strip()
        if re.fullmatch(r'[0-9a-f]{64}', key):
            return key
    except (OSError, UnicodeDecodeError):
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    partial = path.with_name(f'host-key.{os.getpid()}.partial')
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='ascii') as out:
        out.write(key)
    os.replace(partial, path)
    return key


def acquire_lease(workspace):
    """Hold a course for one host, or for setup while it moves the course; refused while another holds it."""
    lease = (workspace / '.learning-host.lock').open('a+b')
    lease.seek(0)
    lease.write(b'0')
    lease.flush()
    lease.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lease.close()
        raise OperationError('host_running', 'Another learning host already owns this course')
    return lease


def own_dir(root):
    """The library's own folder: host bookkeeping, packages waiting to be imported, archived courses and the trash."""
    return Path(root).resolve() / '.throughline'


def course_path(root, name):
    if not isinstance(name, str) or not NAME.match(name):
        raise OperationError('invalid_course_name', 'Course names use lowercase letters, digits and hyphens, for example quantum-v1')
    return Path(root).resolve() / name


def is_course(path):
    return (Path(path) / 'course.sqlite3').is_file()


def fingerprint(path):
    """Changes when course building touches the course: title, position, sources or route. Reads without locking."""
    try:
        db = sqlite3.connect((Path(path) / 'course.sqlite3').resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
        try:
            rows = db.execute("SELECT namespace, key, value FROM documents WHERE namespace IN ('course', 'sources', 'curriculum') ORDER BY namespace, key").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return None
    return hashlib.sha256(repr(rows).encode()).hexdigest()


# How long after a database file was written its stamp is trusted. A file's modification time moves in ticks of the
# file system's clock (a few milliseconds, up to two seconds on FAT), and once the write-ahead log has wrapped, a
# commit rewrites it at the same size; two commits within one tick then leave the same stamp.
SETTLED = 2


def stamp(path):
    """The course database files' sizes and modification times, which every commit changes, or None while a file was
    written too recently for a later commit to be told apart: what was read under a stamp is reused only while the
    stamp is the same."""
    now = time.time_ns()
    def stat(file):
        try:
            info = file.stat()
        except OSError:
            return None
        return (info.st_mtime_ns, info.st_size) if info.st_size else None  # an empty log holds nothing
    database = Path(path) / 'course.sqlite3'
    stamps = stat(database), stat(database.with_name('course.sqlite3-wal'))
    if any(s and now - s[0] < SETTLED * 10**9 for s in stamps):
        return None
    return stamps


# Each course's summary and the database stamp it was read at: the library lists every course on each visit, and most
# have not changed since the last one.
_summaries = {}


def summary(path):
    """What the library shows for one course; reads through operations, never edits."""
    path = Path(path).resolve()
    taken = stamp(path)  # before reading, so a write during the read is seen next time
    cached = _summaries.get(path)
    if cached and taken is not None and cached[0] == taken:
        return dict(cached[1])
    value = _summary(path)
    _summaries[path] = (taken, value)
    return dict(value)


def _summary(path):
    status = execute(path, {'op': 'course.status'})
    curriculum = execute(path, {'op': 'curriculum.view'})
    coverage = execute(path, {'op': 'curriculum.coverage'})
    concepts = {c['id']: c for c in curriculum['concepts']}
    current = (status['position'] or {}).get('concept_id')
    return {'name': path.name,
            'path': str(path),
            'title': status['course']['title'],
            'sources': len(status['sources']),
            'concepts': len(curriculum['route']),
            'needs_review': sum(1 for unit in coverage['units'] if unit['disposition'] in ('needs_review', 'unmapped')),
            'current': concepts.get(current, {}).get('title'),
            'goal': (status.get('profile') or {}).get('goal'),
            'updated': (path / 'course.sqlite3').stat().st_mtime}


def list_courses(root):
    """Every course in the library, most recently studied first, an archived one marked `archived`. Deleted courses wait
    in the trash, which is not in the library's top level, so they are never listed here."""
    root = Path(root)
    if not root.is_dir():
        return []
    hidden = archived(root)
    courses = []
    for path in sorted(p for p in root.iterdir() if p.is_dir() and is_course(p)):
        try:
            courses.append(summary(path))
        except OperationError as exc:
            courses.append({'name': path.name, 'path': str(path.resolve()), 'error': str(exc)})
        except Exception as exc:  # one broken course (a corrupt database, a failing migration) must not hide the others
            log.exception('Could not list the course at %s', path)
            courses.append({'name': path.name, 'path': str(path.resolve()),
                            'error': f'{exc.__class__.__name__}: {exc} (details in the host log)'})
    for course in courses:
        course['archived'] = course['name'] in hidden
    return sorted(courses, key=lambda c: c.get('updated', 0), reverse=True)


# Looking after the library (ADR 0022): archiving hides a course from the list without touching it, and deleting moves
# it to the trash, from where it can be restored. Nothing here removes a course for good; the learner can empty the
# trash folder themselves.

def _settings_file(root):
    return own_dir(root) / 'library.json'


def _settings(root):
    try:
        data = json.loads(_settings_file(root).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


def _save_settings(root, data):
    target = _settings_file(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(temporary, target)


def archived(root):
    """The names of the archived courses: kept in the library's own folder, so archiving never writes to a course."""
    names = _settings(root).get('archived')
    return {name for name in names if isinstance(name, str)} if isinstance(names, list) else set()


def set_archived(root, name, value):
    path = course_path(root, name)
    if not is_course(path):
        raise OperationError('unknown_course', f'No course named {name} in {root}')
    data = _settings(root)
    names = archived(root) - {name}
    data['archived'] = sorted(names | {name} if value else names)
    _save_settings(root, data)
    return {'name': name, 'archived': bool(value)}


def trash_dir(root):
    """Where deleted courses wait: `.throughline/trash/<entry>/<course folder>`, beside a `deleted.json` that says what
    it was. Hidden from the library listing, Studio's file search and imports, which only look at the top level."""
    return own_dir(root) / 'trash'


ENTRY = re.compile(r'^\d{8}-\d{6}-[0-9a-f]{6}$')


def free_name(root, base):
    """`base`, or `base-2`, `base-3`… when a course of that name is already in the library."""
    for number in range(1, 1000):
        candidate = base if number == 1 else f'{base[:60]}-{number}'
        if not (Path(root) / candidate).exists():
            return candidate
    raise OperationError('course_exists', f'Courses named {base} already exist; choose a name')


def _title(path):
    try:
        return (execute(path, {'op': 'course.status'}).get('course') or {}).get('title')
    except Exception:  # a broken course is deleted with the name it is listed under
        return None


def trash(root, name):
    """Move a course to the trash. Refused while another host holds it; the caller closes this host's own first."""
    path = course_path(root, name)
    if not is_course(path):
        raise OperationError('unknown_course', f'No course named {name} in {root}')
    title = _title(path)
    acquire_lease(path).close()  # released before the move, which Windows refuses for an open file
    entry = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    folder = trash_dir(root) / entry
    folder.mkdir(parents=True)
    record = {'name': name, 'title': title, 'deleted': time.time()}
    (folder / 'deleted.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    try:
        os.replace(path, folder / name)
    except OSError as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise OperationError('course_in_use', f'The course could not be moved to the trash: {exc}') from None
    _summaries.pop(path.resolve(), None)
    if name in archived(root):  # a course restored later comes back to the main list
        data = _settings(root)
        data['archived'] = sorted(archived(root) - {name})
        _save_settings(root, data)
    return {'id': entry, 'path': str(folder / name), **record}


def _entry(root, entry):
    if not isinstance(entry, str) or not ENTRY.match(entry):
        raise OperationError('unknown_deleted_course', 'This course is no longer in the trash')
    folder = trash_dir(root) / entry
    try:
        record = json.loads((folder / 'deleted.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        record = None
    name = record.get('name') if isinstance(record, dict) else None
    if not isinstance(name, str) or not NAME.match(name) or not is_course(folder / name):
        raise OperationError('unknown_deleted_course', 'This course is no longer in the trash')
    return folder, {'id': entry, 'name': name, 'title': record.get('title'), 'deleted': record.get('deleted'),
                    'path': str(folder / name)}


def trashed(root):
    """The deleted courses waiting in the trash, most recently deleted first."""
    folder = trash_dir(root)
    if not folder.is_dir():
        return []
    found = []
    for path in folder.iterdir():
        try:
            found.append(_entry(root, path.name)[1])
        except OperationError:
            continue  # not a deleted course: something the learner put there, or one they emptied by hand
    return sorted(found, key=lambda e: e['id'], reverse=True)


def restore(root, entry):
    """Put a deleted course back in the library, under its old name, or a free one when that is taken now."""
    folder, record = _entry(root, entry)
    target = Path(root).resolve() / free_name(root, record['name'])
    os.replace(folder / record['name'], target)
    shutil.rmtree(folder, ignore_errors=True)
    return {**record, 'name': target.name, 'path': str(target), 'trash_path': record['path']}
