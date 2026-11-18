"""A library with one course whose first section's lesson is written, for sharing it as a course package (ADR 0020):
python -m tests.packages_browser_fixture [port]."""
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
course = root / 'quantum-v1'
execute(course, {'op': 'course.init', 'title': 'Introductory Quantum Mechanics'})
execute(course, {'op': 'curriculum.save', 'route': ['wave', 'state'], 'coverage': [], 'concepts': [
    {'id': 'wave', 'title': 'Wave superposition'}, {'id': 'state', 'title': 'Quantum states', 'prerequisites': ['wave']}]})
execute(course, {'op': 'course.profile.save', 'profile': {'goal': 'Pass the midterm', 'depth': 'standard'}})
execute(course, {'op': 'mainline.enter', 'concept_id': 'wave', 'goal': 'Interference', 'next_step': 'Begin', 'request_id': 'w'})
execute(course, {'op': 'lesson.begin', 'id': 'one', 'concept_id': 'wave', 'steps': ['Path amplitudes', 'Adding amplitudes']})
for turn_id, text in (('one', 'Each path carries a complex amplitude.'), ('two', 'Add the amplitudes, then square them.')):
    execute(course, {'op': 'stream.start', 'id': turn_id, 'concept_id': 'wave', 'prompt': 'Teach', 'channel': 'mainline'})
    execute(course, {'op': 'stream.event', 'id': turn_id, 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': text})
    execute(course, {'op': 'stream.event', 'id': turn_id, 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
    execute(course, {'op': 'lesson.step', 'id': 'one', 'turn_id': turn_id})
    execute(course, {'op': 'lesson.reply', 'id': 'one', 'turn_id': turn_id})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Written by the teacher.'})
        emit({'kind': 'complete'})


try:
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'),
          library_root=root, on_ready=lambda port: print(port, flush=True),
          launcher=Launcher(Path(scratch.name + '-none') / 'throughline.desktop', platform='linux'),
          checks=CodexStatus(cheap=lambda: [], probe=lambda: None),
          studio_command=[sys.executable, str(Path(__file__).with_name('fake_studio_server.py')), str(Path(scratch.name + '-studio.log')), 'old'])
finally:
    scratch.cleanup()
