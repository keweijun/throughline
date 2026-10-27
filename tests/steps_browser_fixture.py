"""A section taught in lesson steps (ADR 0009), after a section whose lesson was saved as one reply before steps."""
import json
import re
import tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Quantum · Steps acceptance'})
execute(root, {'op': 'curriculum.save', 'route': ['old', 'wave'], 'coverage': [], 'concepts': [
    {'id': 'old', 'title': 'Classical waves'},
    {'id': 'wave', 'title': 'Wave superposition', 'prerequisites': ['old'],
     'overview': {'core_problem': 'Why do two paths sometimes cancel?', 'steps': ['Path amplitudes', 'Adding amplitudes', 'Probability'],
                  'prior': 'Classical waves', 'next': 'States', 'target_ability': 'Predict interference'}}]})
execute(root, {'op': 'mainline.enter', 'concept_id': 'old', 'goal': 'Waves', 'next_step': 'Read', 'request_id': 'o'})
execute(root, {'op': 'stream.start', 'id': 'old-lesson', 'concept_id': 'old', 'prompt': 'Teach', 'channel': 'mainline'})
execute(root, {'op': 'stream.event', 'id': 'old-lesson', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': '## Classical waves\n\nA long lesson saved as one reply.'})
execute(root, {'op': 'stream.event', 'id': 'old-lesson', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
execute(root, {'op': 'mainline.enter', 'concept_id': 'wave', 'goal': 'Interference', 'next_step': 'Begin', 'request_id': 'w'})

def check(question, right, wrong):
    return {'idea': question, 'question': question, 'correct': 0,
            'options': [{'text': right[0], 'explanation': right[1]}, {'text': wrong[0], 'explanation': wrong[1]}]}


STEPS = {
    1: ('Each path carries a complex amplitude.', {'title': 'Path amplitudes', 'remaining': [
        {'title': 'Complex numbers refresher', 'added': True}, {'title': 'Adding amplitudes'}, {'title': 'Probability'}],
        'check': check('What does a path carry?', ('A complex amplitude', 'Each path contributes an amplitude, not a probability.'),
                       ('A probability', 'Probabilities come only after the amplitudes are added.'))}),
    2: ('Recall that $|z|^2 = z^* z$.', {'remaining': [{'title': 'Adding amplitudes and squaring'}],
        'check': check('What is $|i|^2$?', ('$1$', 'Since $i^* i = 1$.'), ('$-1$', 'That is $i^2$, not $|i|^2$.'))}),
    3: ('Add the amplitudes, then square: $P = |a+b|^2$.', {'remaining': [],
        'check': check('What is added first?', ('The amplitudes', 'Interference comes from adding amplitudes.'),
                       ('The probabilities', 'Adding probabilities loses interference.'))}),
}


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        if 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Find $P$ for $a=b=1/2$.', 'origin': 'self_created', 'source_refs': []}]})
        else:
            number = int(re.search(r'This reply teaches step (\d+)', prompt).group(1))
            if number == 2 and 'previous lesson was interrupted' not in prompt:
                emit({'kind': 'delta', 'text': 'A step that is still being written'})
                cancel.wait(30)
                return
            body, block = STEPS[number]
            if 'aimed at that gap' in prompt:
                body = 'First, a quick fix: a path carries an amplitude. ' + body
            text = body + '\n<lesson-step>' + json.dumps(block) + '</lesson-step>'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
