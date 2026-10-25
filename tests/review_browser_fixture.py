"""Two studied sections whose first review is due: each was solved two days ago (ADR 0008)."""
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
    {'id': 'state', 'title': 'What a state represents'}, {'id': 'superposition', 'title': 'Superposition'}]})
execute(root, {'op': 'mainline.enter', 'request_id': 'enter', 'concept_id': 'superposition', 'goal': 'Superposition', 'next_step': 'Start the lesson'})
# Each section has one exercise solved on its own, as an earlier session in Codex would have recorded it.
for cid in ('state', 'superposition'):
    execute(root, {'op': 'interaction.record', 'id': f'answer-{cid}', 'role': 'user', 'text': 'My answer.', 'concept_id': cid})
    execute(root, {'op': 'interaction.record', 'id': f'feedback-{cid}', 'role': 'assistant', 'text': 'Correct.', 'concept_id': cid})
    execute(root, {'op': 'evidence.assess', 'id': f'pass-{cid}', 'concept_id': cid, 'session_id': 'earlier', 'exercise_id': f'exercise-{cid}',
                   'answer_id': f'answer-{cid}', 'assessment_id': f'feedback-{cid}', 'outcome': 'passed'})
# Two days ago, so the first review (one day after the pass) is due.
store = Store(root)
with store.db:
    for cid in ('state', 'superposition'):
        item = store.get('evidence', f'pass-{cid}')
        store.put('evidence', item['id'], {**item, 'assessed_at': time.time() - 2 * 86400})
store.db.close()


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        if 'Practice only (spaced review)' in prompt:
            text = json.dumps({'questions': [{'question': 'A state is multiplied by $-1$. Does anything you can measure change? Why?'}]})
        elif 'Practice only (chapter quiz)' in prompt:
            text = json.dumps({'questions': [{'question': 'Why must the amplitudes of a superposition be normalized together?', 'tests_concept_ids': ['state', 'superposition']},
                                             {'question': 'Write a new superposition with equal probabilities.', 'tests_concept_ids': ['superposition']}]})
        elif 'Question and help history' in prompt:
            text = json.dumps({'feedback': 'Right: a global phase changes no probability.', 'outcome': 'passed'})
        elif 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Normalize (1, 1).', 'origin': 'self_created', 'source_refs': []}]})
        else:
            text = '## Lesson\n\nA short lesson.'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(Path(root) / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
