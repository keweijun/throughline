"""A course whose later chapters the app builds: python -m tests.chapter_build_browser_fixture."""
import json
import tempfile
import time
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

scratch = tempfile.TemporaryDirectory()
library = Path(scratch.name)
root = library / 'quantum'
execute(root, {'op': 'course.init', 'title': 'Quantum · Build acceptance'})
p = root / 'lecture.md'
p.write_text('A state assigns amplitudes\nOutcomes are eigenvalues\nStates evolve unitarily', encoding='utf-8')
s = execute(root, {'op': 'source.register', 'path': str(p)})['source']
ref = lambda unit: {'source_id': s['id'], 'revision': s['revision'], 'unit_id': unit}
execute(root, {'op': 'curriculum.outline', 'chapters': [
    {'id': 'states', 'title': 'States'}, {'id': 'measurement', 'title': 'Measurement'}, {'id': 'dynamics', 'title': 'Time evolution'}]})
execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'states', 'concepts': [{'id': 'state', 'title': 'What a state represents', 'links': [ref('line-1')]}],
               'coverage': [{**ref('line-1'), 'disposition': 'mapped', 'concept_ids': ['state']}]})

MEASUREMENT = json.dumps({'concepts': [{'id': 'outcomes', 'title': 'Possible outcomes', 'core_question': 'What can a measurement return?',
                                        'objective': 'List the outcomes of a measurement', 'prerequisites': ['state'], 'links': [ref('line-2')]}],
                          'coverage': [{**ref('line-2'), 'disposition': 'mapped', 'concept_ids': ['outcomes']}]})


class Runner:
    """Builds Measurement after a moment; every reply for Time evolution is rejected."""

    def run(self, prompt, cwd, emit, cancel):
        if 'You build one chapter' in prompt:
            time.sleep(1.5)
            text = MEASUREMENT if '(id measurement)' in prompt else '{"concepts": []}'
        else:
            text = '{"questions": []}' if 'Practice only' in prompt else '## Lesson\n\nA short lesson.'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(library / 'settings.json'), library_root=library,
          on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
