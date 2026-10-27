"""A stepped lesson whose second step takes a few seconds to write (ADR 0009): it is written while the learner reads the
first, so Continue shows it at once."""
import json
import re
import tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

WRITING = 3  # seconds the teacher takes over step 2

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Quantum · Prepared steps'})
execute(root, {'op': 'curriculum.save', 'route': ['wave'], 'coverage': [], 'concepts': [
    {'id': 'wave', 'title': 'Wave superposition',
     'overview': {'core_problem': 'Why do two paths sometimes cancel?', 'steps': ['Path amplitudes', 'Probability'],
                  'prior': 'Classical waves', 'next': 'States', 'target_ability': 'Predict interference'}}]})

STEPS = {1: ('Each path carries a complex amplitude.', {'title': 'Path amplitudes', 'remaining': [{'title': 'Probability'}]}),
         2: ('Written while you read: add the amplitudes, then square.', {'remaining': []})}


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        if 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Find $P$ for $a=b=1/2$.', 'origin': 'self_created', 'source_refs': []}]})
        else:
            match = re.search(r'This reply teaches step (\d+)', prompt)
            if not match:
                return
            number = int(match.group(1))
            if number == 2 and cancel.wait(WRITING):
                return
            body, block = STEPS[number]
            text = body + '\n<lesson-step>' + json.dumps(block) + '</lesson-step>'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
