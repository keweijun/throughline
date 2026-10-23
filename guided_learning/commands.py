"""Learner-facing commands that Codex runs on the learner's behalf: setup, open, stop and courses."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from . import library
from .codex import find_codex

SKILL = Path(__file__).resolve().parent / 'skill'
COMMANDS = ('setup', 'open', 'stop', 'courses')


def version():
    try:
        return package_version('codex-guided-learning')
    except PackageNotFoundError:
        return 'development'


def skills_dir():
    return Path(os.environ.get('GUIDED_LEARNING_SKILLS_DIR') or Path.home() / '.agents' / 'skills')


def host_record():
    return library.data_dir() / 'host.json'


def setup(args):
    target = skills_dir() / 'guided-learning'
    marker = target / 'SKILL.md'
    if target.exists() and not (marker.is_file() and 'name: guided-learning' in marker.read_text(encoding='utf-8')):
        print(f'Refusing to replace {target}: it is not the Throughline (guided-learning) skill.', file=sys.stderr)
        return 1
    staging = target.with_name('.guided-learning.tmp')
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(SKILL, staging, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)
    root = library.default_root()
    root.mkdir(parents=True, exist_ok=True)
    print(f'Throughline {version()} is ready.')
    print(f'Codex skill: {target}')
    print(f'Course library: {root}')
    if not find_codex():
        print('Warning: Codex was not found (neither the codex command nor the Codex app); lessons in the interface need it. Set CODEX_CLI_PATH if it is installed somewhere else.')
    try:
        import pypdf  # noqa: F401
    except ImportError:
        print('Warning: PDF support is missing; install the package with the [pdf] extra to read PDFs.')
    print('Next: ask Codex "$guided-learning create a course from <your files>", then "$guided-learning open my course".')
    return 0


def _call(port, method, path, body=None, timeout=2):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method=method,
                                     headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b'{}')


def running():
    """The host started by `open`, if it still answers."""
    try:
        record = json.loads(host_record().read_text(encoding='utf-8'))
        _call(record['port'], 'GET', '/api/library')
        return record
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return None


def _spawn(port):
    log = library.data_dir() / 'host.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'guided_learning.web', '--port', str(port), '--record']
    options = {'stdin': subprocess.DEVNULL, 'stdout': log.open('ab'), 'stderr': subprocess.STDOUT}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    else:
        options['start_new_session'] = True
    process = subprocess.Popen(command, **options)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        record = running()
        if record and record.get('pid') == process.pid:
            return record
        if process.poll() is not None:
            return None
        time.sleep(0.2)
    process.terminate()
    return None


def open_course(args):
    record = running() or _spawn(args.port) or _spawn(0)
    if not record:
        print(f'The learning host did not start; see {library.data_dir() / "host.log"}.', file=sys.stderr)
        return 1
    if args.course:
        try:
            _call(record['port'], 'POST', '/api/library/open', {'name': args.course}, timeout=30)
        except urllib.error.HTTPError as exc:
            print(json.loads(exc.read() or b'{}').get('error', str(exc)), file=sys.stderr)
            return 1
    url = f"http://127.0.0.1:{record['port']}/"
    print(f'Throughline is open at {url}')
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except webbrowser.Error:
            pass
    return 0


def stop(args):
    record = running()
    if not record:
        print('No learning host is running.')
        return 0
    _call(record['port'], 'POST', '/api/shutdown', {})
    print('The learning host is stopping.')
    return 0


def courses(args):
    root = library.default_root()
    print(json.dumps({'ok': True, 'result': {'root': str(root), 'courses': library.list_courses(root)}}, ensure_ascii=True))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(prog='guided-learning')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('setup', help='Install or update the Codex skill and create the course library')
    opener = commands.add_parser('open', help='Start the learning interface in the background and open it')
    opener.add_argument('course', nargs='?', help='Course name in the library')
    opener.add_argument('--port', type=int, default=8765)
    opener.add_argument('--no-browser', action='store_true')
    commands.add_parser('stop', help='Stop the background learning interface')
    commands.add_parser('courses', help='List the courses in the library as JSON')
    args = parser.parse_args(argv)
    return {'setup': setup, 'open': open_course, 'stop': stop, 'courses': courses}[args.command](args)
