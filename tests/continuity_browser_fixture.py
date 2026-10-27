"""A two-section course whose teacher defers side questions to the next section."""
import json
import tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Continuity acceptance'})
execute(root, {'op': 'curriculum.save', 'concepts': [
    {'id': 'wave', 'title': 'Wave superposition', 'objective': 'Add amplitudes from two paths'},
    {'id': 'state', 'title': 'Quantum states', 'objective': 'Explain why phase changes probabilities'}],
    'route': ['wave', 'state'], 'coverage': []})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        if 'Branch decision protocol' in prompt:
            text = ('Briefly: the relative phase decides whether paths reinforce or cancel.\n<teaching-decision>'
                    + json.dumps({'depth': 'short', 'category': 'future', 'rationale': 'Quantum states develops phase',
                                  'suggest_supplement': False, 'supplement_goal': '', 'target_concept_id': 'state'}) + '</teaching-decision>')
        elif 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Add two equal amplitudes with opposite sign.', 'origin': 'self_created', 'source_refs': []}]})
        elif 'Pending explanations' in prompt:
            text = '## Unit overview\n\nStates carry phase.\n\nThis answers your earlier question about phase in full.'
        else:
            text = '## Unit overview\n\nTwo paths add.\n\nAmplitudes add before squaring.'
        if 'This reply teaches step' in prompt:
            text += '\n<lesson-step>{"remaining": []}</lesson-step>'  # a one-step lesson
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
