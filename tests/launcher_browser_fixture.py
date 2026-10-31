"""A library with one course, a launcher in a scratch folder and a Codex that is not signed in until checked again:
python -m tests.launcher_browser_fixture [port]."""
import sys
import tempfile
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
asked = []


def codex_checks():
    """The learner signs in between the first check and the next."""
    asked.append(1)
    return [checks.result('codex', True, 'codex-cli 1.0 (/bin/codex)'), checks.result('signed_in', len(asked) > 1, '')]


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Lesson.'})
        emit({'kind': 'complete'})


try:
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 0, runner=Runner(), settings=TeacherSettings(root / 'config' / 'settings.json'),
          library_root=root / 'library', launcher=Launcher(entry, platform='linux', desktop=root / 'Desktop', start=lambda command: None),
          checks=codex_checks, on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
