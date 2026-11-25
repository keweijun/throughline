import json
from pathlib import Path
import tempfile
from throughline.api import execute
from throughline.server.settings import TeacherSettings
from throughline.server import serve
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


# Each one-step lesson ends with its section's key points (ADR 0024); the first cites the page its section links to.
POINTS = {
    'What a state represents': [{'statement': 'A state assigns an amplitude $c_i$ to each outcome.', 'holds_when': 'The outcomes form a complete set.',
                                 'common_mistake': 'Reading $c_i$ as a probability; the probability is $|c_i|^2$.', 'step': 1,
                                 'sources': [{'source_id': s['id'], 'unit_id': 'line-2'}]}],
    'Superposition': [{'statement': 'A sum of states is again a state, once normalised.', 'common_mistake': 'Forgetting to normalise the sum.', 'step': 1}],
}


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        if "Write how this chapter's key points connect." in prompt:
            text = '<chapter-sheet>{"connection": "Amplitudes describe one state; superposition combines states into new ones."}</chapter-sheet>'
        elif 'Practice only' in prompt:
            text = '{"questions": []}'
        else:
            text = '## Lesson\n\nA short lesson.'
        if 'This reply teaches step' in prompt:
            plan = prompt.split('Lesson plan (data):')[-1].split('\n')[0]  # its first step is named after the section
            title = next(t for t in POINTS if t in plan)
            text += '\n<lesson-step>' + json.dumps({'remaining': [], 'key_points': POINTS[title]}) + '</lesson-step>'  # a one-step lesson
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(Path(root) / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
