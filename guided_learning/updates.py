"""Whether a newer Throughline is available. Installing it is Codex's job (README), so the interface hands it off."""
import os
import re
import urllib.request

from .commands import version
from .store import OperationError

# The install command fetches main, so main's declared version is the latest one.
LATEST = 'https://raw.githubusercontent.com/keweijun/throughline/main/pyproject.toml'
VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


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


def check():
    current, latest = version(), latest_version()
    return {'version': current, 'latest': latest, 'available': newer(latest, current)}
