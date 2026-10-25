from pathlib import Path
import tempfile
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Quantum · Chapters acceptance'})
p = root / 'lecture.md'
p.write_text('# States\nA state assigns amplitudes\n# Measurement\nOutcomes are eigenvalues', encoding='utf-8')
s = execute(root, {'op': 'source.register', 'path': str(p)})['source']
ref = lambda unit: {'source_id': s['id'], 'revision': s['revision'], 'unit_id': unit}
execute(root, {'op': 'curriculum.outline', 'chapters': [
    {'id': 'states', 'title': 'States', 'summary': 'What a quantum state represents and how amplitudes combine.'},
    {'id': 'measurement', 'title': 'Measurement'},
    {'id': 'dynamics', 'title': 'Time evolution'}]})
execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'states', 'concepts': [
    {'id': 'state', 'title': 'What a state represents', 'links': [ref('line-2')]},
    {'id': 'superposition', 'title': 'Superposition', 'prerequisites': ['state']}],
    'coverage': [{**ref('line-2'), 'disposition': 'mapped', 'concept_ids': ['state']}, {**ref('line-1'), 'disposition': 'needs_review', 'reason': 'Heading only', 'concept_ids': ['state']}]})
execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'measurement', 'concepts': [
    {'id': 'outcomes', 'title': 'Possible outcomes', 'prerequisites': ['superposition'], 'links': [ref('line-4')]}]})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        text = '{"questions": []}' if 'Practice only' in prompt else ('## Chapter recap\n\nThe chapter in one line: states and their superpositions.' if 'Chapter recap' in prompt else '## Lesson\n\nA short lesson.')
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(Path(root) / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
