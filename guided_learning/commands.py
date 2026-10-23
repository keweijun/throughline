"""Learner-facing commands that Codex runs on the learner's behalf: setup, open, stop and courses."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import uuid
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

from . import library
from .codex import find_codex

SKILL = Path(__file__).resolve().parent / 'skill'
ICON = Path(__file__).resolve().parent / 'web_dist' / 'favicon.svg'
PROJECT_MARKER = '<!-- Written by guided-learning setup; rerunning setup replaces this file. -->'
FIRST_PROMPT = '$guided-learning Help me create my first Throughline course.'
LANGUAGES = {'en': 'English', 'zh-CN': 'Simplified Chinese'}
WELCOME_TITLES = {'en': 'Welcome to Throughline', 'zh-CN': '欢迎使用贯学'}
WELCOME_NAMING = {'en': 'Call the app Throughline. Its library buttons are labelled "Add files in Codex", "Review in Codex" and "New course in Codex".',
                  'zh-CN': 'Call the app 贯学 (Throughline). Its library buttons are labelled "在 Codex 中添加文件", "在 Codex 中核对" and "在 Codex 中新建课程". The Codex project and the launcher are named "Throughline".'}


def launcher_hint():
    if os.name == 'nt':
        return 'search for "Throughline" in the Start menu'
    if sys.platform == 'darwin':
        return 'open Throughline from Launchpad, Spotlight or the Applications folder in your home folder'
    return 'open Throughline from your desktop app menu'


def welcome_prompt(root, launcher, language):
    """Facts for the welcome chat; Codex words them, so they arrive in the learner's language."""
    how_to_open = launcher_hint() if launcher else 'ask Codex in this project to "open Throughline"'
    return f'''$guided-learning Throughline was just installed and this is the learner's first chat in the Throughline project.
Write a short, friendly welcome in {LANGUAGES[language]}, using headings or a list, and include all of these facts. {WELCOME_NAMING[language]}

- What Throughline is: a study app that turns their own PDFs, Markdown notes and problem sets into a guided course with lessons, questions about any passage, the original pages beside each explanation, and practice. Codex teaches in the background; they do not need Codex open to study.
- Where things are: their Throughline folder is {root}. This chat lives in the Codex project "Throughline", which points at that folder; course work happens in this project.
- To create the first course: in this chat, attach their files (or name the folder they are in) and say in a sentence what they want to learn and why, for example an exam or a project. Codex proposes a course name and route, says what still needs checking, and opens the course in Throughline.
- To study afterwards: {how_to_open}. The library there lists every course, and its Codex buttons come back to this project to add files or review pages.
- The app can switch between English and Simplified Chinese from the language selector at the top.

End by asking which files they want to start with. Do not run any commands or read any files.'''
PROJECT_AGENTS = PROJECT_MARKER + '''
# Throughline course library

This folder is the learner's Throughline course library. Each subfolder containing `course.sqlite3` is one course.

- Use the `$guided-learning` skill for all course work: creating a course, adding files, rebuilding a route, reviewing pages.
- Copy a course's source files into `<course>/inputs/` before registering them. Never edit `course.sqlite3`, `sources/` or `.throughline/` by hand.
- When course work is done, run `guided-learning open <course>` so the learner can study it in the Throughline app.
- Studying happens in the app. Teach in this chat only when the learner asks for it.

## When the learner has not said what to do

New learners often start with a bare request such as "help me create my first course". Reply briefly, in the learner's language:

1. Throughline turns their own documents (PDFs, Markdown notes, problem sets) into a guided course; Codex builds it here, and they study it in the Throughline app.
2. To create a course, attach the files to this chat or give the folder they are in, and say in a sentence what they want to learn (for example "quantum mechanics up to perturbation theory, for my exam").
3. Codex then proposes a course name and route, shows what still needs checking, and opens the course in the app.

Then wait for the files and the goal. Do not start building until both are clear.
'''
COMMANDS = ('setup', 'open', 'stop', 'courses')


def version():
    try:
        return package_version('codex-guided-learning')
    except PackageNotFoundError:
        return 'development'


def skills_dir():
    return Path(os.environ.get('GUIDED_LEARNING_SKILLS_DIR') or Path.home() / '.agents' / 'skills')


def host_record():
    return library.state_dir() / 'host.json'


def windowless_python():
    """pythonw.exe on Windows, so neither the host nor the launcher opens a console window."""
    if os.name == 'nt':
        gui = Path(sys.executable).with_name('pythonw.exe')
        if gui.is_file():
            return str(gui)
    return sys.executable


def project_link(root):
    return 'codex://new?' + urllib.parse.urlencode({'prompt': FIRST_PROMPT, 'path': str(root)}, quote_via=urllib.parse.quote)


def write_project_agents(root):
    target = root / 'AGENTS.md'
    if target.exists() and not target.read_text(encoding='utf-8').startswith(PROJECT_MARKER):
        return False
    target.write_text(PROJECT_AGENTS, encoding='utf-8')
    return True


def install_launcher():
    """An app-menu entry that runs `guided-learning open`; returns where it was put, or None."""
    if os.name == 'nt':
        executable = windowless_python()
        folder = Path(os.environ.get('APPDATA', Path.home())) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'Throughline.lnk'
        script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GL_LNK);"
                  "$s.TargetPath=$env:GL_EXE;$s.Arguments='-m guided_learning open';$s.Description='Throughline';$s.Save()")
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True,
                                env={**os.environ, 'GL_LNK': str(target), 'GL_EXE': executable},
                                creationflags=subprocess.CREATE_NO_WINDOW)
        return target if result.returncode == 0 else None
    command = f'"{sys.executable}" -m guided_learning open'
    if sys.platform == 'darwin':
        app = Path.home() / 'Applications' / 'Throughline.app' / 'Contents'
        (app / 'MacOS').mkdir(parents=True, exist_ok=True)
        (app / 'Info.plist').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Throughline</string>
<key>CFBundleIdentifier</key><string>io.github.keweijun.throughline</string>
<key>CFBundleExecutable</key><string>Throughline</string>
<key>CFBundlePackageType</key><string>APPL</string>
</dict></plist>
''', encoding='utf-8')
        launcher = app / 'MacOS' / 'Throughline'
        launcher.write_text(f'#!/bin/sh\nexec {command}\n', encoding='utf-8')
        launcher.chmod(0o755)
        return app.parent
    folder = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'applications'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'throughline.desktop'
    target.write_text(f'[Desktop Entry]\nType=Application\nName=Throughline\nComment=Study your courses\n'
                      f'Exec={command}\nIcon={ICON}\nTerminal=false\nCategories=Education;\n', encoding='utf-8')
    return target


def welcome_thread(root, launcher, language):
    """Create the Throughline project in the Codex app and send the first chat in it, so the learner opens it already answered."""
    from .codex import CodexRunner, ensure_project
    events = []
    try:
        project = ensure_project(root, 'Throughline')
        CodexRunner(timeout=180, ephemeral=False, project_id=project, name=WELCOME_TITLES[language]).run(welcome_prompt(root, launcher, language), root, events.append, threading.Event())
    except Exception:
        return None
    thread = next((e['id'] for e in events if e['kind'] == 'thread'), None)
    return thread if any(e['kind'] == 'complete' for e in events) else None


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
    wrote_agents = write_project_agents(root)
    launcher = None if args.no_launcher else install_launcher()
    print(f'Throughline {version()} is ready.')
    print(f'Codex skill: {target}')
    print(f'Course library and Codex project: {root}')
    if not wrote_agents:
        print(f'Kept your own {root / "AGENTS.md"}; add a note that course work uses the $guided-learning skill.')
    if launcher:
        print(f'Launcher: {launcher}')
    elif not args.no_launcher:
        print('Warning: the launcher could not be created; open Throughline with "guided-learning open".')
    thread = None if args.no_welcome or not find_codex() else welcome_thread(root, launcher, args.language)
    if thread:
        print(f'Open the welcome chat in the Codex app: codex://threads/{thread}')
    print(f'Open the project in the Codex app: {project_link(root)}')
    print(f'With the Codex CLI, start codex in {root}.')
    if not find_codex():
        print('Warning: Codex was not found (neither the codex command nor the Codex app); lessons in the interface need it. Set CODEX_CLI_PATH if it is installed somewhere else.')
    try:
        import pypdf  # noqa: F401
    except ImportError:
        print('Warning: PDF support is missing; install the package with the [pdf] extra to read PDFs.')
    print('Next: in the Throughline project, send "Help me create my first Throughline course", then attach your PDFs or notes and say what you want to learn.')
    print('To study, open Throughline from the launcher.')
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
    log = library.state_dir() / 'host.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [windowless_python(), '-m', 'guided_learning.web', '--port', str(port), '--record']
    launch_id = str(uuid.uuid4())
    options = {'stdin': subprocess.DEVNULL, 'stderr': subprocess.STDOUT,
               'env': {**os.environ, 'GUIDED_LEARNING_LAUNCH_ID': launch_id}}
    if os.name == 'nt':
        # Not DETACHED_PROCESS: a venv's python.exe is a launcher, and a detached launcher's child gets a visible console.
        options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        options['start_new_session'] = True
    with log.open('ab') as output:
        process = subprocess.Popen(command, stdout=output, **options)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        record = running()
        if record and record.get('launch_id') == launch_id:
            return record
        if process.poll() is not None:
            return None
        time.sleep(0.2)
    process.terminate()
    return None


def open_course(args):
    record = running() or _spawn(args.port) or _spawn(0)
    if not record:
        print(f'The learning host did not start; see {library.state_dir() / "host.log"}.', file=sys.stderr)
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
    setup_parser = commands.add_parser('setup', help='Install or update the Codex skill, the course library and the launcher')
    setup_parser.add_argument('--no-launcher', action='store_true')
    setup_parser.add_argument('--no-welcome', action='store_true', help='Do not start the welcome chat in Codex')
    setup_parser.add_argument('--language', choices=tuple(LANGUAGES), default='en', help='Language of the welcome chat')
    opener = commands.add_parser('open', help='Start the learning interface in the background and open it')
    opener.add_argument('course', nargs='?', help='Course name in the library')
    opener.add_argument('--port', type=int, default=8765)
    opener.add_argument('--no-browser', action='store_true')
    commands.add_parser('stop', help='Stop the background learning interface')
    commands.add_parser('courses', help='List the courses in the library as JSON')
    args = parser.parse_args(argv)
    return {'setup': setup, 'open': open_course, 'stop': stop, 'courses': courses}[args.command](args)
