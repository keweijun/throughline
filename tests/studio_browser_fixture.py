"""A course host whose Studio talks to the scripted App Server in tests/fake_studio_server.py, or with
STUDIO_REAL=1 to the real Codex (for trying Studio by hand)."""
import os
import sys
import tempfile
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server import serve
from guided_learning.server.settings import TeacherSettings

scratch = tempfile.TemporaryDirectory()
library = Path(scratch.name) / 'library'
course = library / 'waves'
course.mkdir(parents=True)
execute(course, {'op': 'course.init', 'title': 'Waves'})
execute(course, {'op': 'curriculum.save', 'concepts': [{'id': 'wave', 'title': 'Wave superposition'}], 'route': ['wave'], 'coverage': []})
(course / 'inputs').mkdir()
(course / 'inputs' / 'waves.md').write_text('# Waves\n', encoding='utf-8')
fake = [sys.executable, str(Path(__file__).with_name('fake_studio_server.py')), str(Path(scratch.name) / 'studio.log')]


class Runner:
    """Lessons suggest a change to the course, which opens in Studio (ADR 0016)."""

    def run(self, prompt, cwd, emit, cancel):
        text = 'A wave.'
        if 'Practice only' not in prompt:
            text += '\n<course-change>{"request":"Add a section on interference after Wave superposition"}</course-change>'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(course, port=0, runner=Runner(), settings=TeacherSettings(Path(scratch.name) / 'config' / 'settings.json'),
          library_root=library, studio_command=None if os.environ.get('STUDIO_REAL') else fake,
          on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
