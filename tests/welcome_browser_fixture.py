"""A fresh install: an empty library, a launcher in a scratch folder and Studio on the scripted App Server in
tests/fake_studio_server.py: python -m tests.welcome_browser_fixture [port]."""
import sys
import tempfile
from pathlib import Path

from throughline import checks
from throughline.launcher import Launcher
from throughline.server import serve
from throughline.server.settings import TeacherSettings

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
(root / 'library').mkdir()
entry = root / 'applications' / 'throughline.desktop'
entry.parent.mkdir()
entry.write_text('[Desktop Entry]\nName=Throughline\n', encoding='utf-8')


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Lesson.'})
        emit({'kind': 'complete'})


try:
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 0, runner=Runner(), settings=TeacherSettings(root / 'config' / 'settings.json'),
          library_root=root / 'library', launcher=Launcher(entry, platform='linux', desktop=root / 'Desktop', start=lambda command: None, output=lambda command: None),
          checks=checks.CodexStatus(cheap=lambda: [checks.result('codex', True, 'codex-cli 1.0 (/bin/codex)')],
                                    probe=lambda: checks.result('answers', True, '', model='gpt-6-luna', seconds=0)),
          on_ready=lambda port: print(port, flush=True),
          studio_command=[sys.executable, str(Path(__file__).with_name('fake_studio_server.py')), str(root / 'studio.log')])
finally:
    scratch.cleanup()
