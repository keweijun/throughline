"""Learner-facing commands that Codex runs on the learner's behalf: setup, open, stop and courses."""
import argparse
import json
import os
import shutil
import subprocess
import sys
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
ICONS = Path(__file__).resolve().parent / 'icons'
LIBRARY_MARKER = '<!-- Written by guided-learning setup; rerunning setup replaces this file. -->'
LANGUAGES = ('en', 'zh-CN')
LAUNCHER_HINTS = {
    'nt': {'en': 'search for "Throughline" in the Start menu', 'zh-CN': '在开始菜单中搜索“Throughline”'},
    'darwin': {'en': 'open Throughline from Launchpad, Spotlight or the Applications folder', 'zh-CN': '从启动台、聚焦搜索或“应用程序”文件夹打开 Throughline'},
    'darwin-home': {'en': 'open Throughline from Launchpad, Spotlight, or Applications in your home folder', 'zh-CN': '从启动台、聚焦搜索或个人文件夹中的“应用程序”打开 Throughline'},
    'linux': {'en': 'open Throughline from your app menu', 'zh-CN': '从应用菜单中打开 Throughline'},
    None: {'en': 'run `throughline` in a terminal, or ask Codex "$throughline open"', 'zh-CN': '在终端运行 `throughline`，或在 Codex 中输入“$throughline 打开”'},
}
# Where a macOS launcher goes when the shared Applications folder is writable; tests point it elsewhere.
APPLICATIONS = Path('/Applications')
BUNDLE_ID = 'io.github.keweijun.throughline'


def platform():
    return 'nt' if os.name == 'nt' else 'darwin' if sys.platform == 'darwin' else 'linux'


def launcher_hint(launcher, language):
    """How to open Throughline next time, in the words of this platform."""
    kind = platform() if launcher else None
    if kind == 'darwin' and Path(launcher).parent != APPLICATIONS:
        kind = 'darwin-home'
    return LAUNCHER_HINTS[kind][language]


def welcome(root, launcher, language, opened=False):
    """The short guide setup prints for Codex to show the learner; the app explains the rest itself."""
    hint = launcher_hint(launcher, language)
    # "New course" names the library's button both before and after Studio (#109 settles the final wording).
    if language == 'zh-CN':
        first = ('贯学已在浏览器中打开：在课程库中选择“New course”（新建课程），建你的第一门课。' if opened
                 else '现在打开贯学，在课程库中选择“New course”（新建课程），建你的第一门课。')
        return f"""## 贯学（Throughline）{version()} 已安装

- 贯学文件夹：`{root}`，每门课程是其中一个子文件夹。
- 以后打开贯学：{hint}。

{first}"""
    first = ('Throughline is open in your browser: make your first course from the library with **New course**.' if opened
             else 'Open Throughline now and make your first course from the library with **New course**.')
    return f"""## Throughline {version()} is installed

- Your Throughline folder: `{root}`. Each course is a folder inside it.
- To open Throughline next time, {hint}.

{first}"""


LIBRARY_AGENTS = LIBRARY_MARKER + '''
# Throughline course library

This folder is the learner's Throughline course library. Each subfolder containing `course.sqlite3` is one course.

- Use the `$throughline` skill for all course work: creating a course, adding files, rebuilding a route, reviewing pages.
- Copy a course's source files into `<course>/inputs/` before registering them. Never edit `course.sqlite3`, `sources/` or `.throughline/` by hand.
- When course work is done, run `guided-learning open <course>` so the learner can study it in the Throughline app.
- Studying happens in the app. If the learner asks to be taught in this chat, open the course in the app instead.

## When the learner has not said what to do

New learners often start with a bare request such as "help me create my first course". Reply briefly, in the learner's language:

1. Throughline turns their own documents (PDFs, Markdown notes, problem sets) into a guided course; Codex builds it here, and they study it in the Throughline app.
2. To create a course, attach the files to this chat or give the folder they are in, and say in a sentence what they want to learn (for example "quantum mechanics up to perturbation theory, for my exam").
3. Codex reads the files and says what it found, then asks a few quick questions with options and a recommendation (goal and deadline, how well they know each prerequisite, with an optional quick check, how much detail, what to emphasize or skip, how they like to learn); "ok" takes the recommendations. It proposes a course name and route that fit the answers, shows what still needs checking, and opens the course in the app.

If they are unsure what to learn, suggest goals that fit their files. Then wait for the files and the goal before building, and follow the `$throughline` skill's intake once both are clear.
'''
COMMANDS = ('setup', 'open', 'stop', 'courses')


def version():
    # Before 0.5.1 the package was named codex-guided-learning.
    for name in ('throughline', 'codex-guided-learning'):
        try:
            return package_version(name)
        except PackageNotFoundError:
            pass
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


def write_library_agents(root):
    target = root / 'AGENTS.md'
    if target.exists() and not target.read_text(encoding='utf-8').startswith(LIBRARY_MARKER):
        return False
    target.write_text(LIBRARY_AGENTS, encoding='utf-8')
    return True


def mac_applications():
    """The shared Applications folder when this user can write to it, otherwise Applications in the home folder."""
    return APPLICATIONS if os.access(APPLICATIONS, os.W_OK) else Path.home() / 'Applications'


def launcher_path():
    """Where this platform's launcher is, or would be once setup adds it."""
    kind = platform()
    if kind == 'nt':
        return Path(os.environ.get('APPDATA', Path.home())) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Throughline.lnk'
    if kind == 'darwin':
        for folder in (APPLICATIONS, Path.home() / 'Applications'):
            if (folder / 'Throughline.app').is_dir():
                return folder / 'Throughline.app'
        return mac_applications() / 'Throughline.app'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'applications' / 'throughline.desktop'


def _ours_on_mac(app):
    try:
        return BUNDLE_ID in (app / 'Contents' / 'Info.plist').read_text(encoding='utf-8')
    except OSError:
        return False


def install_launcher():
    """An app-menu entry that runs `guided-learning open`; returns where it was put, or None."""
    if platform() == 'nt':
        executable = windowless_python()
        target = launcher_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GL_LNK);"
                  "$s.TargetPath=$env:GL_EXE;$s.Arguments='-m guided_learning open';$s.Description='Throughline';"
                  "$s.IconLocation=$env:GL_ICON+',0';$s.Save()")
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True,
                                env={**os.environ, 'GL_LNK': str(target), 'GL_EXE': executable, 'GL_ICON': str(ICONS / 'throughline.ico')},
                                creationflags=subprocess.CREATE_NO_WINDOW)
        return target if result.returncode == 0 else None
    command = f'"{sys.executable}" -m guided_learning open'
    if platform() == 'darwin':
        bundle = mac_applications() / 'Throughline.app'
        for other in (APPLICATIONS / 'Throughline.app', Path.home() / 'Applications' / 'Throughline.app'):
            if other != bundle and _ours_on_mac(other):  # one launcher only, so Spotlight finds one Throughline
                shutil.rmtree(other, ignore_errors=True)
        app = bundle / 'Contents'
        (app / 'MacOS').mkdir(parents=True, exist_ok=True)
        (app / 'Info.plist').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Throughline</string>
<key>CFBundleIdentifier</key><string>{BUNDLE_ID}</string>
<key>CFBundleExecutable</key><string>Throughline</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>throughline</string>
</dict></plist>
''', encoding='utf-8')
        (app / 'Resources').mkdir(exist_ok=True)
        shutil.copyfile(ICONS / 'throughline.icns', app / 'Resources' / 'throughline.icns')
        launcher = app / 'MacOS' / 'Throughline'
        launcher.write_text(f'#!/bin/sh\nexec {command}\n', encoding='utf-8')
        launcher.chmod(0o755)
        return bundle
    target = launcher_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    icon = ICONS / 'throughline.png'
    target.write_text(f'[Desktop Entry]\nType=Application\nName=Throughline\nComment=Study your courses\n'
                      f'Exec={command}\nIcon={icon}\nTerminal=false\nCategories=Education;\n', encoding='utf-8')
    return target


def migrate(root):
    """Move courses from earlier default locations into `root`; returns (moved, skipped) course names."""
    moved, skipped = [], []
    for old in library.legacy_roots():
        if not old.is_dir() or old.resolve() == root.resolve():
            continue
        try:  # a host started from the old location still holds its courses
            record = json.loads((old / '.throughline' / 'host.json').read_text(encoding='utf-8'))
            _call(record['port'], 'POST', '/api/shutdown', {})
            time.sleep(3)
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            pass
        for course in sorted(p for p in old.iterdir() if p.is_dir() and library.is_course(p)):
            if (root / course.name).exists():
                skipped.append(str(course))
                continue
            try:
                shutil.move(str(course), str(root / course.name))
                moved.append(course.name)
            except OSError:
                skipped.append(str(course))
        agents = old / 'AGENTS.md'
        if agents.is_file() and agents.read_text(encoding='utf-8').startswith(LIBRARY_MARKER):
            agents.unlink()
        shutil.rmtree(old / '.throughline', ignore_errors=True)
        try:
            old.rmdir()
        except OSError:
            pass
    return moved, skipped


def ours(folder, name):
    marker = folder / 'SKILL.md'
    return marker.is_file() and f'name: {name}' in marker.read_text(encoding='utf-8')


def setup(args):
    target = skills_dir() / 'throughline'
    if target.exists() and not ours(target, 'throughline'):
        print(f'Refusing to replace {target}: it is not the Throughline skill.', file=sys.stderr)
        return 1
    previous = skills_dir() / 'guided-learning'  # the skill's name before 0.5
    if previous.exists() and ours(previous, 'guided-learning'):
        shutil.rmtree(previous, ignore_errors=True)
    staging = target.with_name('.throughline.tmp')
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(SKILL, staging, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)
    root = library.default_root()
    root.mkdir(parents=True, exist_ok=True)
    wrote_agents = write_library_agents(root)
    migrated, kept = migrate(root)
    launcher = None if args.no_launcher else install_launcher()
    print(f'Throughline {version()} is ready.')
    print(f'Codex skill: {target}')
    print(f'Course library: {root}')
    if migrated:
        print(f'Moved {len(migrated)} course(s) into {root}: {", ".join(migrated)}')
    for path in kept:
        print(f'Left {path} where it is: a course with that name exists in {root}, or it is in use.')
    if not wrote_agents:
        print(f'Kept your own {root / "AGENTS.md"}; add a note that course work uses the $throughline skill.')
    if launcher:
        print(f'Launcher: {launcher}')
    elif not args.no_launcher:
        print('Warning: the launcher could not be created; open Throughline with "guided-learning open".')
    if not find_codex():
        print('Warning: Codex was not found (neither the codex command nor the Codex app); lessons in the interface need it. Set CODEX_CLI_PATH if it is installed somewhere else.')
    try:
        import pypdf  # noqa: F401
    except ImportError:
        print('Warning: PDF support is missing; install the package with the [pdf] extra to read PDFs.')
    opened = False if args.no_open else open_app()
    print()
    print('Show the learner this welcome guide as written:')
    print()
    print(welcome(root, launcher, args.language, opened))
    return 0


def open_app():
    """Start the host and open the library in the browser, as setup's last step. Never fails setup."""
    try:
        record = running() or _spawn(8765) or _spawn(0)
        if not record:
            print(f'Throughline did not start; see {library.state_dir() / "host.log"}.')
            return False
        url = f"http://127.0.0.1:{record['port']}/"
        print(f'Throughline is open at {url}')
        # With no display, webbrowser would pick a console browser and take over the terminal Codex is reading.
        if platform() == 'linux' and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            return False
        return bool(webbrowser.open(url))
    except Exception as exc:  # setup has done its work; opening the app is a convenience
        print(f'Throughline could not be opened ({exc}); open it with the launcher.')
        return False


def _call(port, method, path, body=None, timeout=2):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method=method,
                                     headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b'{}')


def running():
    """The host started by `open`, if it still answers on its recorded port."""
    try:
        record = json.loads(host_record().read_text(encoding='utf-8'))
        try:
            health = _call(record['port'], 'GET', '/api/health')
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            _call(record['port'], 'GET', '/api/library')  # a host from before /api/health existed
            return record
        return record if health.get('pid') == record.get('pid') else None
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return None


def _error_text(exc):
    """What the host said went wrong with a request, or that it did not answer."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            return json.loads(exc.read() or b'{}').get('error') or str(exc)
        except ValueError:
            return str(exc)
    return f'The learning host did not answer ({getattr(exc, "reason", exc)}).'


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
        except (urllib.error.URLError, OSError) as exc:
            print(_error_text(exc), file=sys.stderr)
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
    try:
        _call(record['port'], 'POST', '/api/shutdown', {})
    except urllib.error.HTTPError as exc:
        print(_error_text(exc), file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError):
        print('No learning host is running.')  # it stopped between the check and the request
        return 0
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
    setup_parser.add_argument('--no-open', action='store_true', help='Do not open Throughline when setup is done')
    setup_parser.add_argument('--language', choices=LANGUAGES, default='en', help='Language of the welcome guide')
    opener = commands.add_parser('open', help='Start the learning interface in the background and open it')
    opener.add_argument('course', nargs='?', help='Course name in the library')
    opener.add_argument('--port', type=int, default=8765)
    opener.add_argument('--no-browser', action='store_true')
    commands.add_parser('stop', help='Stop the background learning interface')
    commands.add_parser('courses', help='List the courses in the library as JSON')
    args = parser.parse_args(argv)
    return {'setup': setup, 'open': open_course, 'stop': stop, 'courses': courses}[args.command](args)
