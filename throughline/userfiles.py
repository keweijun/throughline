"""Per-user JSON files (teacher settings, Studio's record, the library's own settings), which more than one
Throughline process may change at once: two versions side by side, or a host beside a command.

Each change reads the file, changes it and writes it back atomically while holding a lock on a file beside it, so a
writer never replaces the file with a copy read before another writer's change and drops what that one saved. The lock
is reentrant within a process, so a change can be built from smaller ones; hold it only for the read, change and
write, never across a Codex call or other slow work."""
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

if os.name == 'nt':
    import msvcrt
else:
    import fcntl

_guard = threading.Lock()
_held = {}  # lock file -> [this process's in-process lock, how deeply its owning thread holds it, the open lock file]


def _lock_os(handle):
    if os.name == 'nt':
        # msvcrt locks bytes from the current position; LK_LOCK gives up after about ten seconds, so keep trying.
        while True:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                time.sleep(0.05)
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_os(handle):
    if os.name == 'nt':
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def locked(path):
    """Hold the cross-process lock for the per-user file at `path` (`<name>.lock` beside it) until the block ends."""
    path = Path(path)
    lock_path = path.with_name(f'{path.name}.lock').absolute()
    with _guard:
        entry = _held.setdefault(str(lock_path), [threading.RLock(), 0, None])
    with entry[0]:
        if entry[1] == 0:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(lock_path, 'a+b')
            try:
                _lock_os(handle)
            except BaseException:
                handle.close()
                raise
            entry[2] = handle
        entry[1] += 1
        try:
            yield
        finally:
            entry[1] -= 1
            if entry[1] == 0:
                handle, entry[2] = entry[2], None
                try:
                    _unlock_os(handle)
                finally:
                    handle.close()


def write_json(path, data):
    """Write a per-user JSON file atomically, keeping any keys this version does not know, which a newer
    Throughline (run before a downgrade, or beside this one) may have saved there. Returns the written object.

    A caller that read the file to build `data` holds `locked(path)` around both, so nothing another process writes
    between that read and this write is lost."""
    path = Path(path)
    with locked(path):
        try:
            kept = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            kept = {}
        merged = {**(kept if isinstance(kept, dict) else {}), **data}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
        temporary.write_text(json.dumps(merged, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    return merged
