"""A course where Studio has answered a drill's hand-off with a mock exam and written a sheet (issue #229)."""
import json
import tempfile
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
op = lambda **r: execute(root, r)
op(op='course.init', title='Quantum · Studio in Review')
op(op='curriculum.outline', chapters=[{'id': 'states', 'title': 'States'}])
op(op='curriculum.chapter.save', chapter_id='states', concepts=[{'id': 'state', 'title': 'What a state represents'}, {'id': 'superposition', 'title': 'Superposition'}])
op(op='mainline.enter', request_id='enter', concept_id='superposition', goal='Superposition', next_step='Start the lesson')
for turn, cid in (('lesson-state', 'state'),):
    op(op='stream.start', id=turn, concept_id=cid, prompt='Teach', record_user=False)
    op(op='stream.event', id=turn, attempt=1, sequence=1, kind='final', text='## States\n\nA state is a unit vector.')
    op(op='stream.event', id=turn, attempt=1, sequence=2, kind='complete')
# A drill whose reply offered Studio a mock exam, sent, and answered.
op(op='drill.create', id='session-1', kind='drill')
op(op='drill.add_turn', id='session-1', turn_id='t-1', message='Can you make me a mock exam on states?')
op(op='stream.start', id='t-1', concept_id='state', channel='drill', prompt='Can you make me a mock exam on states?', record_user=True)
op(op='stream.event', id='t-1', attempt=1, sequence=1, kind='final', text='Studio can write you one from the course exercises.')
op(op='stream.event', id='t-1', attempt=1, sequence=2, kind='complete')
op(op='drill.offer', id='session-1', turn_id='t-1', label='A mock exam on States', request='Write me a mock exam on the chapter States.')
op(op='handoff.save', id='drill:t-1', place={'kind': 'drill', 'session': 'session-1', 'turn': 't-1'}, label='A mock exam on States',
   request='Write me a mock exam on the chapter States.', thread_id='thread-done')
op(op='drill.write', id='mock-states', title='Mock exam: States', exam=True, note='Two questions; about twenty minutes.', handoff_id='drill:t-1', questions=[
    {'kind': 'apply', 'question': 'Normalise $(1, i)$ and give each probability.', 'parts': ['(a) the norm', '(b) the probabilities'], 'tests_concept_ids': ['state'], 'marks': 6},
    {'kind': 'recall', 'question': 'A state is multiplied by $-1$. Does any probability change?', 'idea': 'global phase', 'tests_concept_ids': ['state'], 'marks': 2,
     'options': [{'text': 'No', 'explanation': 'Probabilities are squared magnitudes.'}, {'text': 'Yes', 'explanation': 'A global sign cancels.'}], 'correct': 0}])
op(op='sheet.save', id='formulas-states', title='Formula sheet: States', scope={'chapter_ids': ['states']},
   markdown='## Normalisation\n\n$$\\langle\\psi|\\psi\\rangle = 1$$\n\n## Probabilities\n\n$P_i = |c_i|^2$, unchanged by a global phase.')


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        text = json.dumps({'feedback': 'Right.', 'outcome': 'passed'}) if 'Question and help history' in prompt else 'Fine.'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(Path(root) / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
