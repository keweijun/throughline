"""Whether a newer Throughline is available. Installing it is Codex's job (README), so the interface hands it off."""
import os
import re
import threading
import time
import urllib.request

from .commands import version
from .store import OperationError

# The install command fetches main, so main's declared version is the latest one.
LATEST = 'https://raw.githubusercontent.com/keweijun/throughline/main/pyproject.toml'
VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
# The interface checks on every launch, so a found version is kept for a while rather than asked of GitHub each time.
KEEP = 6 * 3600
_found = {}
_lock = threading.Lock()


def _parts(text):
    return tuple(int(n) for n in re.findall(r'\d+', text))


def newer(latest, current):
    """True when `latest` is a later release than `current`; a development checkout is never behind."""
    if not _parts(current) or not _parts(latest):
        return False
    return _parts(latest) > _parts(current)


def latest_version(timeout=10):
    url = os.environ.get('GUIDED_LEARNING_UPDATE_URL') or LATEST
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            text = response.read(64 * 1024).decode('utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise OperationError('update_check_failed', f'Could not reach GitHub to check for updates ({getattr(exc, "reason", exc)})') from exc
    match = VERSION.search(text)
    if not match:
        raise OperationError('update_check_failed', 'GitHub did not say which version is the latest')
    return match.group(1)


def check(fresh=False):
    """Compares with main's version; a version found in the last few hours is reused unless `fresh`. Failures are not kept."""
    with _lock:
        if fresh or time.monotonic() - _found.get('at', -KEEP) >= KEEP:
            _found.update(latest=latest_version(), at=time.monotonic())
        latest = _found['latest']
    current = version()
    return {'version': current, 'latest': latest, 'available': newer(latest, current)}
