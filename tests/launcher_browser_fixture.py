"""A library with one course, a launcher in a scratch folder and a Codex that cannot answer until checked again:
python -m tests.launcher_browser_fixture [port]."""
import sys
import tempfile
import time
from pathlib import Path

from guided_learning import checks
from guided_learning.api import execute
from guided_learning.launcher import Launcher
from guided_learning.server import serve
from guided_learning.server.settings import TeacherSettings

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root / 'library' / 'quantum', {'op': 'course.init', 'title': 'Quantum'})
execute(root / 'library' / 'quantum', {'op': 'curriculum.save', 'concepts': [{'id': 'first', 'title': 'Superposition'}], 'route': ['first'], 'coverage': []})
entry = root / 'applications' / 'throughline.desktop'
entry.parent.mkdir()
entry.write_text('[Desktop Entry]\nName=Throughline\n', encoding='utf-8')
probed = []


def probe():
    """Codex cannot answer the first time and can once the learner has fixed it; no real model is asked."""
    probed.append(1)
    time.sleep(0.3)
    error = '' if len(probed) > 1 else 'Codex rejected initialization or generation: 401 Unauthorized'
    return checks.result('answers', not error, error, model='gpt-6-luna', seconds=0.3)


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Lesson.'})
        emit({'kind': 'complete'})


try:
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 0, runner=Runner(), settings=TeacherSettings(root / 'config' / 'settings.json'),
          library_root=root / 'library', launcher=Launcher(entry, platform='linux', desktop=root / 'Desktop', start=lambda command: None),
          checks=checks.CodexStatus(cheap=lambda: [checks.result('codex', True, 'codex-cli 1.0 (/bin/codex)')], probe=probe), on_ready=lambda port: print(port, flush=True),
          # A Codex without Studio's methods, so no real Codex starts.
          studio_command=[sys.executable, str(Path(__file__).with_name('fake_studio_server.py')), str(root / 'studio.log'), 'old'])
finally:
    scratch.cleanup()
