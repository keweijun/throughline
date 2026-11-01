"""A course whose lesson and exercise carry runnable Python cells (the python add-on, ADR 0013). The browser test serves
a fake Pyodide in place of the CDN."""
import json
import tempfile
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server import serve
from guided_learning.server.settings import TeacherSettings

LESSON = '''Squares of a few numbers:

```python-run
print('hello')
```
'''
EXERCISE = {'question': "Print the square of 7.\n\n```python-run\n# your code here\nprint('fortynine')\n```", 'parts': ['Print the square of 7.'],
            'origin': 'self_created', 'source_refs': []}

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Python'})
execute(root, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'Squares'}], 'route': ['a'], 'coverage': []})
execute(root, {'op': 'widgets.save', 'ids': ['python']})
execute(root, {'op': 'mainline.enter', 'concept_id': 'a', 'goal': 'Square numbers', 'next_step': 'practice', 'request_id': 'a'})
job = {'id': 'questions', 'concept_id': 'a', 'action': 'generate'}
execute(root, {'op': 'practice.job', 'job': job})
execute(root, {'op': 'stream.start', 'id': job['id'], 'concept_id': 'a', 'prompt': 'Exercise service', 'channel': 'practice', 'record_user': False})
execute(root, {'op': 'stream.event', 'id': job['id'], 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': json.dumps({'questions': [EXERCISE]})})
execute(root, {'op': 'stream.event', 'id': job['id'], 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
execute(root, {'op': 'practice.complete', 'id': job['id']})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        text = json.dumps({'questions': [EXERCISE]}) if 'Practice only' in prompt else LESSON
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
