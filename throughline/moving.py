"""Moving a course folder with nothing written to it meanwhile: deleting it to the library's trash, or setup moving it
from an old library location (ADR 0022)."""
import errno
import os
import shutil
import sqlite3
import uuid
from pathlib import Path

from .store import OperationError

# Left in a course while it moves. Every write checks for it under the write lock (`api._write`).
MOVING = '.moving'


def try_lock(path):
    """The open file at `path`, locked for this process alone, or None while another holds it. The operating system
    lets go of the lock when its holder ends, crashed or not."""
    lock = Path(path).open('a+b')
    lock.seek(0)
    lock.write(b'0')
    lock.flush()
    lock.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return None
    return lock


def _move_lock(path):
    """Held by the operation moving the course at `path` for as long as it runs. It is beside the course, in the
    library's own folder, not in it: Windows refuses to move a folder holding an open file."""
    path = Path(path)
    return path.parent / '.throughline' / 'moving' / f'{path.name}.lock'


def _in_trash(path):
    return path.parent.parent.name == 'trash' and path.parent.parent.parent.name == '.throughline'


def leftover(path):
    """Whether `MOVING` in the course at `path` was left by a move that ended without finishing (the process was killed
    between marking the course and moving it), so the course never left its folder. A course in the trash keeps its
    marker until it is restored. Called under the course's write lock, which a move marks the course under, so no move
    can mark it while this looks."""
    path = Path(path)
    if _in_trash(path):
        return False
    lock_path = _move_lock(path)
    if not lock_path.is_file():
        return True  # no move made with this version ever ran here; 0.55 and earlier left no lock
    try:
        lock = try_lock(lock_path)
    except OSError:
        return False
    if lock is None:
        return False  # the move is running
    lock.close()
    return True


def move_course(path, target, what):
    """Move the course at `path` to `target`, refused with `course_in_use` (and nothing moved) when the folder cannot
    be moved, which Windows says while a file in it is open. `what` names the move in that message.

    The move holds a lock beside the course from start to end and leaves `MOVING` in the course under its write lock
    before it moves: a write already running (Codex registering a source from the command line, say) finishes first,
    files and all, and every later one sees the marker, or no course at the old path, and is refused (`api._write`). A
    move that dies halfway leaves its marker with no one holding the lock, which the next write clears (`leftover`)."""
    path, target = Path(path), Path(target)
    lock_path = _move_lock(path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock = try_lock(lock_path)
    except OSError as exc:
        raise OperationError('course_in_use', f'{what}: {exc}') from None
    if lock is None:
        raise OperationError('course_busy', f'{what}: the course is already being moved')
    try:
        _mark(path, what)
        try:
            _move(path, target)
        except OSError as exc:
            (path / MOVING).unlink(missing_ok=True)
            raise OperationError('course_in_use', f'{what}: {exc}') from None
    finally:
        lock.close()


def _mark(path, what):
    db = sqlite3.connect(path / 'course.sqlite3', timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE')
        (path / MOVING).write_text(f'{os.getpid()}\n', encoding='utf-8')
        db.rollback()
    except sqlite3.Error as exc:
        raise OperationError('course_in_use', f'{what}: {exc}') from None
    finally:
        db.close()


def _move(path, target):
    """Rename the folder; between file systems, copy it and rename the original aside first, so a folder Windows will
    not let go of stays whole where it was and the copy is removed."""
    try:
        os.replace(path, target)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
    partial = target.with_name(f'.{target.name}.{uuid.uuid4().hex[:8]}.partial')
    aside = path.with_name(f'.{path.name}.{uuid.uuid4().hex[:8]}.moved')
    try:
        shutil.copytree(path, partial)
        os.replace(path, aside)
    except OSError:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    try:
        os.replace(partial, target)
    except OSError:
        os.replace(aside, path)
        shutil.rmtree(partial, ignore_errors=True)
        raise
    shutil.rmtree(aside, ignore_errors=True)
