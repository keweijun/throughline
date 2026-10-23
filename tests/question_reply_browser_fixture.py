"""A durable follow-up whose host stopped before creating the answer stream."""
import tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server import serve
from guided_learning.server.settings import TeacherSettings

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Follow-up recovery'})
execute(root, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'Section A'}], 'route': ['a'], 'coverage': []})
execute(root, {'op': 'mainline.enter', 'concept_id': 'a', 'goal': 'Understand', 'next_step': 'Practice', 'request_id': 'p'})
execute(root, {'op': 'branch.begin', 'id': 'q', 'question': 'Original question'})
execute(root, {'op': 'stream.start', 'id': 'branch:q', 'concept_id': 'a', 'channel': 'sidequestion', 'prompt': 'Original question'})
execute(root, {'op': 'stream.event', 'id': 'branch:q', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': 'Original answer'})
execute(root, {'op': 'stream.event', 'id': 'branch:q', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
execute(root, {'op': 'branch.reply', 'id': 'q', 'reply_id': 'r', 'question': 'Explain more', 'selection': 'Original answer'})

class Runner:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Recovered answer'})
        emit({'kind': 'complete'})

try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
