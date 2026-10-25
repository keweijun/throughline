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
    'darwin': {'en': 'open Throughline from Launchpad, Spotlight, or Applications in your home folder', 'zh-CN': '从启动台、聚焦搜索或个人文件夹中的“应用程序”打开 Throughline'},
    'linux': {'en': 'open Throughline from your app menu', 'zh-CN': '从应用菜单中打开 Throughline'},
    None: {'en': 'ask Codex "$throughline open"', 'zh-CN': '在 Codex 中输入“$throughline 打开”'},
}


def welcome(root, launcher, language):
    """The guide setup prints for Codex to show the learner in the install chat."""
    platform = None if not launcher else 'nt' if os.name == 'nt' else 'darwin' if sys.platform == 'darwin' else 'linux'
    hint = LAUNCHER_HINTS[platform][language]
    if language == 'zh-CN':
        return f"""## 欢迎使用贯学（Throughline）

贯学把你自己的 PDF、Markdown 笔记和习题集变成有引导的课程：分节讲解、针对任意段落提问、讲解旁边就是原文页面，还有练习。讲课由 Codex 在后台完成，学习时不需要打开 Codex。

**在 Codex 里用 `$throughline`**
在任意 Codex 对话中以 `$throughline` 开头，就能创建或修改课程，例如：
- `$throughline 用这些文件建一门课`（再附上文件，或写出它们所在的文件夹）
- `$throughline 把这份习题加入 quantum`
- `$throughline 打开 quantum`

建课时，Codex 会先问几个问题（目标和截止时间、先修知识掌握情况、希望讲多细），再给出学习路线，说明哪些内容还需核对，然后在贯学中打开课程。

**文件在哪里**
贯学文件夹：`{root}`，每门课程是其中一个子文件夹。

**之后怎么学习**
{hint}。课程库会列出所有课程，“在 Codex 中…”按钮会打开一段已经写好请求的 Codex 对话。界面顶部可以在 English 和简体中文之间切换。

想现在就建第一门课吗？在这里输入 `$throughline`，附上你的文件即可。"""
    return f"""## Welcome to Throughline

Throughline turns your own PDFs, Markdown notes and problem sets into a guided course: lessons section by section, questions about any passage, the original page beside each explanation, and practice. Codex teaches in the background, so you don't need Codex open to study.

**Use `$throughline` in Codex**
Start any Codex chat with `$throughline` to create or change a course, for example:
- `$throughline make a course from these files` (then attach them, or name the folder they're in)
- `$throughline add this problem set to quantum`
- `$throughline open quantum`

When building a course, Codex first asks a few questions (your goal and deadline, how well you know the prerequisites, how much detail you want), then proposes a route, says what still needs checking, and opens the course in Throughline.

**Where things are**
Your Throughline folder: `{root}`. Each course is a folder inside it.

**Study afterwards**
To open Throughline, {hint}. The library lists every course; its "in Codex" buttons open a Codex chat with the request already written. Switch between English and Simplified Chinese at the top.

Want to build your first course now? Type `$throughline` here and attach your files."""


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
3. Codex asks a few quick questions (goal and deadline, how well they know each prerequisite, how much detail they want), proposes a course name and route that fit the answers, shows what still needs checking, and opens the course in the app.

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


def write_library_agents(root):
    target = root / 'AGENTS.md'
    if target.exists() and not target.read_text(encoding='utf-8').startswith(LIBRARY_MARKER):
        return False
    target.write_text(LIBRARY_AGENTS, encoding='utf-8')
    return True


def install_launcher():
    """An app-menu entry that runs `guided-learning open`; returns where it was put, or None."""
    if os.name == 'nt':
        executable = windowless_python()
        folder = Path(os.environ.get('APPDATA', Path.home())) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'Throughline.lnk'
        script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:GL_LNK);"
                  "$s.TargetPath=$env:GL_EXE;$s.Arguments='-m guided_learning open';$s.Description='Throughline';"
                  "$s.IconLocation=$env:GL_ICON+',0';$s.Save()")
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True,
                                env={**os.environ, 'GL_LNK': str(target), 'GL_EXE': executable, 'GL_ICON': str(ICONS / 'throughline.ico')},
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
<key>CFBundleIconFile</key><string>throughline</string>
</dict></plist>
''', encoding='utf-8')
        (app / 'Resources').mkdir(exist_ok=True)
        shutil.copyfile(ICONS / 'throughline.icns', app / 'Resources' / 'throughline.icns')
        launcher = app / 'MacOS' / 'Throughline'
        launcher.write_text(f'#!/bin/sh\nexec {command}\n', encoding='utf-8')
        launcher.chmod(0o755)
        return app.parent
    folder = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'applications'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'throughline.desktop'
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
    print()
    print('Show the learner this welcome guide as written:')
    print()
    print(welcome(root, launcher, args.language))
    return 0


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
    setup_parser.add_argument('--language', choices=LANGUAGES, default='en', help='Language of the welcome guide')
    opener = commands.add_parser('open', help='Start the learning interface in the background and open it')
    opener.add_argument('course', nargs='?', help='Course name in the library')
    opener.add_argument('--port', type=int, default=8765)
    opener.add_argument('--no-browser', action='store_true')
    commands.add_parser('stop', help='Stop the background learning interface')
    commands.add_parser('courses', help='List the courses in the library as JSON')
    args = parser.parse_args(argv)
    return {'setup': setup, 'open': open_course, 'stop': stop, 'courses': courses}[args.command](args)
