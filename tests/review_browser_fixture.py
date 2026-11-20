"""Two studied sections, practised ten days ago; Superposition, the current section, builds on the first (ADR 0014)."""
import json
import tempfile
import time
from pathlib import Path

from guided_learning.api import execute
from guided_learning.store import Store
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Quantum · Review acceptance'})
execute(root, {'op': 'curriculum.outline', 'chapters': [{'id': 'states', 'title': 'States'}]})
execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'states', 'concepts': [
    {'id': 'state', 'title': 'What a state represents'}, {'id': 'superposition', 'title': 'Superposition', 'prerequisites': ['state']}]})
execute(root, {'op': 'mainline.enter', 'request_id': 'enter', 'concept_id': 'superposition', 'goal': 'Superposition', 'next_step': 'Start the lesson'})
# Each section has one exercise solved on its own, as an earlier session in Codex would have recorded it.
for cid in ('state', 'superposition'):
    execute(root, {'op': 'interaction.record', 'id': f'answer-{cid}', 'role': 'user', 'text': 'My answer.', 'concept_id': cid})
    execute(root, {'op': 'interaction.record', 'id': f'feedback-{cid}', 'role': 'assistant', 'text': 'Correct.', 'concept_id': cid})
    execute(root, {'op': 'evidence.assess', 'id': f'pass-{cid}', 'concept_id': cid, 'session_id': 'earlier', 'exercise_id': f'exercise-{cid}',
                   'answer_id': f'answer-{cid}', 'assessment_id': f'feedback-{cid}', 'outcome': 'passed'})
# The first section was taught in a lesson too, which ended with its key points (ADR 0024).
execute(root, {'op': 'stream.start', 'id': 'lesson-state', 'concept_id': 'state', 'prompt': 'Teach', 'record_user': False})
execute(root, {'op': 'stream.event', 'id': 'lesson-state', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': '## States\n\nA state is a unit vector.'})
execute(root, {'op': 'stream.event', 'id': 'lesson-state', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
execute(root, {'op': 'key_points.save', 'concept_id': 'state', 'turn_id': 'lesson-state', 'origin': 'lesson', 'points': [
    {'statement': 'A state is a unit vector; multiplying it by a phase changes no probability.', 'holds_when': 'The phase is global.',
     'common_mistake': 'Treating a relative phase as global.', 'turn_id': 'lesson-state'}]})
store = Store(root)
with store.db:
    for cid in ('state', 'superposition'):
        item = store.get('evidence', f'pass-{cid}')
        store.put('evidence', item['id'], {**item, 'assessed_at': time.time() - 10 * 86400})
    turn = store.get('streams', 'lesson-state')
    store.put('streams', 'lesson-state', {**turn, 'started_at': time.time() - 10 * 86400})
store.db.close()

RECALL = {'kind': 'recall', 'idea': 'global phase', 'question': 'A state is multiplied by $-1$. Does any probability change?',
          'options': [{'text': 'No', 'explanation': 'Every probability is a squared magnitude, so the sign cancels.'},
                      {'text': 'Yes, they all flip sign', 'explanation': 'Probabilities are never negative.'}],
          'correct': 0, 'tests_concept_ids': ['state']}
APPLY = {'kind': 'apply', 'question': 'Normalize $(1, i)$ and say what each probability is.', 'tests_concept_ids': ['state', 'superposition']}


EARLIER = {'kind': 'apply', 'question': 'Asked again from Superposition: normalize (1, 1).', 'tests_concept_ids': ['superposition']}


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        if 'drilling the learner' in prompt:
            said = prompt.rsplit('The learner now says:\n', 1)[-1]
            # A warm-up tests only the prerequisites of the section it comes before; a chapter drill asks an earlier
            # exercise again first.
            if 'warm-up before the learner starts' in prompt:
                text, questions = 'A quick warm-up.', [RECALL]
            elif 'drills one chapter' in prompt:
                text, questions = 'One you have seen before, then a new one.', [EARLIER, APPLY]
            elif 'measurement' in said.lower():
                text, questions = 'Measurement is not studied yet, so here is one on phases instead.', [RECALL]
            elif 'Drill me.' in said and '"teacher":' in prompt:
                text, questions = 'Two more.', [{**RECALL, 'question': 'Two states differ by a phase $e^{i\\pi/3}$. Same probabilities?'}, APPLY]
            else:
                text, questions = 'Two quick ones.', [RECALL, APPLY]
            text += '\n<drill-questions>' + json.dumps({'questions': questions}) + '</drill-questions>'
        elif 'Question and help history' in prompt:
            text = json.dumps({'feedback': 'Right: each probability is 1/2.', 'outcome': 'passed'})
        elif 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Normalize (1, 1).', 'origin': 'self_created', 'source_refs': []}]})
        else:
            text = '## Lesson\n\nA short lesson.'
        if 'This reply teaches step' in prompt:
            text += '\n<lesson-step>{"remaining": []}</lesson-step>'  # a one-step lesson
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(Path(root) / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
