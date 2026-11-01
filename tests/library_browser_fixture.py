"""A course library with two courses and one being built: python -m tests.library_browser_fixture [port]."""
import sys
import tempfile
from pathlib import Path

from guided_learning.api import execute
from guided_learning.checks import CodexStatus
from guided_learning.launcher import Launcher
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
for name, title, section in (('quantum-v1', 'Introductory Quantum Mechanics', 'Superposition'), ('linear-algebra', 'Linear Algebra', 'Eigenvectors')):
    execute(root / name, {'op': 'course.init', 'title': title})
    execute(root / name, {'op': 'curriculum.save', 'concepts': [{'id': 'first', 'title': section}], 'route': ['first'], 'coverage': []})
execute(root / 'thermo', {'op': 'course.init', 'title': 'Thermodynamics'})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Lesson.'})
        emit({'kind': 'complete'})


try:
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'),
          library_root=root, on_ready=lambda port: print(port, flush=True),
          # Not this computer's launcher or Codex: the library's card and checks have their own fixture.
          launcher=Launcher(Path(scratch.name + '-none') / 'throughline.desktop', platform='linux'), 
          checks=CodexStatus(cheap=lambda: [], probe=lambda: None),
          # A Codex without Studio's methods: the library keeps its Codex-chat buttons, and no real Codex starts.
          studio_command=[sys.executable, str(Path(__file__).with_name('fake_studio_server.py')), str(Path(scratch.name + '-studio.log')), 'old'])
finally:
    scratch.cleanup()
