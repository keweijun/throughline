"""Whether a newer Throughline is available, and installing it with a background Codex.

Codex follows the README's install steps, as it does when asked in a chat; a second, deterministic copy of them
would have to handle running from the environment it replaces (ADR 0004).
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from .codex import find_codex
from .commands import detached, version
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


# Codex stops this host, so the update outlives it; its status lives in files the next host reads.
STATUS, RESULT, SCHEMA, LOG = 'update.json', 'update-result.json', 'update-schema.json', 'update.log'
# An update that has not finished by then has failed, whatever Codex is still doing.
GIVE_UP = 20 * 60
ANSWER = {
    'type': 'object',
    'properties': {'ok': {'type': 'boolean'}, 'version': {'type': 'string'}, 'message': {'type': 'string'}},
    'required': ['ok', 'version', 'message'],
    'additionalProperties': False,
}
LANGUAGES = {'en': 'English', 'zh-CN': 'Simplified Chinese'}
_install_lock = threading.Lock()
# The Codex this host started; only this host can tell that it exited early, since the next one never knew it.
_process = {}


def prompt(current, latest, port, course=None, language='en'):
    reopen = f'guided-learning open {course} --no-browser --port {port}' if course else f'guided-learning open --no-browser --port {port}'
    return f"""Update https://github.com/keweijun/throughline

Throughline asked for this update from its own Settings and runs it in the background: nobody reads this chat, so do not ask anything, and finish on your own.

- Installed now: version {current}, running from {sys.executable}. The latest is {latest}.
- Follow the README's steps for installing or updating Throughline, with two changes: run `guided-learning setup --no-open` (no welcome guide is needed), and when it is done start Throughline again for the browser tab that is waiting for it: `{reopen}`.
- Your last message is shown to the learner: set `ok` to whether Throughline {latest} or newer is installed and running, `version` to what `guided-learning --version` prints, and `message` to one or two plain sentences in {LANGUAGES.get(language, 'English')}: what you installed, or what went wrong and what the learner can do about it.
"""


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def _codex_error(log):
    """The last error Codex reported in its JSON event log, if any."""
    message = None
    try:
        lines = Path(log).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('type') in ('error', 'turn.failed'):
            error = event.get('error') if isinstance(event.get('error'), dict) else event
            message = error.get('message') or message
    return message


def install(folder, port, course=None, language='en', command=None):
    """Starts a background Codex that installs the latest version and opens Throughline again on `port`."""
    folder = Path(folder)
    with _install_lock:
        if (progress(folder) or {}).get('state') == 'running':
            raise OperationError('update_running', 'Throughline is already updating')
        found = check()
        if not found['available']:
            raise OperationError('update_not_available', 'You have the latest version')
        codex = command or find_codex()
        if not codex:
            raise OperationError('codex_missing', 'Codex was not found, so it cannot install the update')
        folder.mkdir(parents=True, exist_ok=True)
        _write(folder / SCHEMA, ANSWER)
        (folder / RESULT).unlink(missing_ok=True)
        record = {'state': 'running', 'from': found['version'], 'to': found['latest'], 'started': time.time(),
                  'log': str(folder / LOG)}
        _write(folder / STATUS, record)
        arguments = [codex, 'exec', '--ephemeral', '--skip-git-repo-check', '--json',
                     '--dangerously-bypass-approvals-and-sandbox',  # it installs software and writes outside any workspace
                     '--output-schema', str(folder / SCHEMA), '--output-last-message', str(folder / RESULT),
                     prompt(found['version'], found['latest'], port, course, language)]
        try:
            with (folder / LOG).open('wb') as output:
                _process['codex'] = subprocess.Popen(arguments, cwd=folder, stdout=output, **detached())
        except OSError as exc:
            (folder / STATUS).unlink(missing_ok=True)
            raise OperationError('codex_missing', f'Codex could not be started ({exc})') from exc
        return record


def _fail(folder, record, message):
    record = {**record, 'state': 'failed', 'message': message}
    _write(folder / STATUS, record)
    return record


def progress(folder):
    """The update last started here: running, or failed with Codex's reason; None once it is installed or never asked."""
    folder = Path(folder)
    record = _read(folder / STATUS)
    if not isinstance(record, dict) or record.get('state') not in ('running', 'failed'):
        return None
    if not newer(record.get('to', ''), version()):
        # This is the new version (or the learner installed it another way): nothing is left to report.
        for name in (STATUS, RESULT, SCHEMA):
            (folder / name).unlink(missing_ok=True)
        return None
    if record['state'] == 'failed':
        return record
    answer = _read(folder / RESULT)
    if isinstance(answer, dict):
        return _fail(folder, record, answer.get('message') or f'Codex finished without installing the update; see {record["log"]}')
    process = _process.get('codex')
    if process is not None and process.poll() is not None:
        detail = _codex_error(record['log'])
        return _fail(folder, record, f'Codex stopped before installing the update: {detail}' if detail
                     else f'Codex stopped before installing the update; see {record["log"]}')
    if time.time() - record.get('started', 0) > GIVE_UP:
        return _fail(folder, record, f'The update did not finish in {GIVE_UP // 60} minutes; see {record["log"]}')
    return record
