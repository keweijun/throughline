"""A realistic course for browsing the interface: python -m tests.demo_course_fixture [port]."""
import json
import sys
import tempfile
import time
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
from tests.sample_pdf import write_pdf

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Introductory Quantum Mechanics'})
notes = root / 'notes.md'
notes.write_text('# Probability\nThe wavefunction must satisfy the normalization condition.\nAmplitudes add before squaring.', encoding='utf-8')
lecture = root / 'lecture-2.pdf'
write_pdf(lecture, [
    ['Lecture 2: Superposition', '', 'Two paths reach the same detector.', 'Each path carries a complex amplitude a or b.'],
    ['2.1 Adding amplitudes', '', 'The total amplitude is a + b.', 'The probability is the squared magnitude |a + b|^2.',
     'Expanding gives |a|^2 + |b|^2 + 2 Re(a* b).', 'The last term is the interference term.'],
    ['2.2 Phase', '', 'When the phases differ by pi the paths cancel.', 'Exercise 2.3: find P(phi) for equal amplitudes.'],
])
md = execute(root, {'op': 'source.register', 'path': str(notes)})['source']
# The lecture PDF was exported from a slide deck (ADR 0015).
deck = root / 'lecture-2.pptx'
deck.write_bytes(b'PK\x03\x04 slides')
pdf = execute(root, {'op': 'source.register', 'path': str(lecture), 'converted_from': str(deck)})['source']
md_ref = {'source_id': md['id'], 'revision': md['revision'], 'unit_id': 'line-2'}
pdf_ref = {'source_id': pdf['id'], 'revision': pdf['revision'], 'unit_id': 'page-2'}
exercise_ref = {'source_id': pdf['id'], 'revision': pdf['revision'], 'unit_id': 'page-3'}
concepts = [
    {'id': 'wave', 'title': 'Wave superposition', 'links': [md_ref, pdf_ref], 'exercises': [{**exercise_ref, 'required_concepts': ['wave']}],
     'overview': {'core_problem': 'Why do two paths sometimes cancel instead of adding up?',
                  'steps': ['Represent each path by a complex amplitude', 'Add amplitudes, not probabilities', 'Square the magnitude to get a probability'],
                  'prior': 'Builds on classical waves and complex numbers', 'next': 'leads into quantum states and measurement',
                  'target_ability': 'Predict an interference pattern from two path amplitudes.'}},
    {'id': 'state', 'title': 'Quantum states and measurement', 'prerequisites': ['wave']},
    {'id': 'operators', 'title': 'Operators and observables', 'prerequisites': ['state']},
    {'id': 'schrodinger', 'title': 'The Schrödinger equation', 'prerequisites': ['operators']},
    {'id': 'well', 'title': 'Particle in a box', 'prerequisites': ['schrodinger']},
]
execute(root, {'op': 'curriculum.save', 'concepts': concepts, 'route': [c['id'] for c in concepts], 'coverage': []})
execute(root, {'op': 'mainline.enter', 'concept_id': 'wave', 'goal': 'Understand amplitudes through wave superposition',
               'next_step': 'Explain interference through superposition of two paths.', 'request_id': 'w'})
LESSON = ('## Unit overview\n\nTwo paths reach the same detector. Classically we would add the *intensities*; quantum mechanically we add '
          '**probability amplitudes** first. [Source ' + pdf['id'] + ' / page-2]\n\n'
          '1. Each path contributes a complex amplitude $a$ or $b$.\n2. The total amplitude is $a+b$.\n3. The probability is the squared magnitude:\n\n'
          '$$P=|a+b|^2=|a|^2+|b|^2+2\\,\\mathrm{Re}(a^*b)$$\n\nThe last term is the **interference term**. [Source ' + md['id'] + ' / line-2]\n\n'
          '> When the phases differ by $\\pi$, the interference term is negative and the paths cancel.\n\n'
          '| Phase difference | Interference |\n| --- | --- |\n| $0$ | Constructive |\n| $\\pi$ | Destructive |\n\n### Worked example\n\n'
          'Let $a=b=\\tfrac{1}{2}$. Then $P=1$. If instead $b=-\\tfrac12$, then $P=0$ even though each path alone gives $\\tfrac14$.\n\n'
          'This is the core reason quantum probabilities behave differently from classical ones.')


def complete(identifier, channel, text, concept='wave', record_user=True):
    execute(root, {'op': 'stream.start', 'id': identifier, 'concept_id': concept, 'prompt': 'Teach', 'channel': channel, 'record_user': record_user})
    execute(root, {'op': 'stream.event', 'id': identifier, 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': text})
    execute(root, {'op': 'stream.event', 'id': identifier, 'attempt': 1, 'sequence': 2, 'kind': 'complete'})


complete('lesson1', 'mainline', LESSON)
execute(root, {'op': 'practice.job', 'job': {'id': 'questions', 'concept_id': 'wave', 'action': 'generate'}})
complete('questions', 'practice', json.dumps({'questions': [
    {'question': 'Two paths have amplitudes $a=\\tfrac{1}{\\sqrt2}$ and $b=\\tfrac{1}{\\sqrt2}e^{i\\phi}$. Find $P(\\phi)$.', 'origin': 'source', 'source_refs': [exercise_ref]},
    {'question': 'For which $\\phi$ is the detector completely dark?', 'origin': 'self_created', 'source_refs': []}]}), record_user=False)
execute(root, {'op': 'practice.complete', 'id': 'questions'})
execute(root, {'op': 'branch.begin', 'id': 'br1', 'question': 'Why is the cross term $2\\,\\mathrm{Re}(a^*b)$ and not $2ab$?',
               'selection': 'The last term is the interference term.', 'selected_turn_id': 'lesson1', 'main_turn_id': 'lesson1'})
complete('branch:br1', 'sidequestion', 'Because $|z|^2=z^*z$. Expanding $(a+b)^*(a+b)$ gives $a^*b+ab^*=2\\,\\mathrm{Re}(a^*b)$.\n'
         '<teaching-decision>{"depth":"short","category":"local","rationale":"Local algebra; no route change needed","suggest_supplement":false,"supplement_goal":""}</teaching-decision>')
execute(root, {'op': 'branch.decide', 'id': 'br1', 'decision': {'depth': 'short', 'category': 'local', 'rationale': 'Local algebra; no route change needed', 'suggest_supplement': False}})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        if 'Practice only' in prompt:
            emit({'kind': 'final', 'text': json.dumps({'feedback': 'Expand $|a+b|^2$ using $|z|^2=z^*z$.', 'outcome': 'needs_work'})})
            emit({'kind': 'complete'})
            return
        text = ''
        for i in range(12):
            if cancel.is_set():
                return
            piece = f'Streaming paragraph {i} explaining the idea with $x_{i}$.\n\n'
            text += piece
            emit({'kind': 'delta', 'text': piece})
            time.sleep(0.15)
        if 'This reply teaches step' in prompt:
            text += '\n<lesson-step>{"remaining": []}</lesson-step>'  # a one-step lesson
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=int(sys.argv[1]) if len(sys.argv) > 1 else 0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'),
          on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
