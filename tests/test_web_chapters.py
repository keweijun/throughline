import tempfile
import threading
import unittest
from pathlib import Path
from guided_learning.api import execute
from support import host_client, settle


class Runner:
    """Captures each prompt and completes immediately, or once `gate` opens; practice turns return no exercises and a
    lesson is taught in one step."""

    def __init__(self):
        self.prompts = []
        self.gate = None

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if self.gate:
            self.gate.wait(5)
        text = '{"questions": []}' if 'Practice only' in prompt else 'Lesson text'
        if 'This reply teaches step' in prompt:
            text += '\n<lesson-step>{"remaining": []}</lesson-step>'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


class Chapters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        execute(self.root, {'op': 'course.init', 'title': 'Quantum'})
        execute(self.root, {'op': 'curriculum.outline', 'chapters': [{'id': 'one', 'title': 'States'}, {'id': 'two', 'title': 'Measurement'}]})
        execute(self.root, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [{'id': 'a', 'title': 'What a state represents'}, {'id': 'b', 'title': 'Superposition'}]})
        execute(self.root, {'op': 'curriculum.chapter.save', 'chapter_id': 'two', 'concepts': [{'id': 'c', 'title': 'Outcomes', 'prerequisites': ['a']}]})
        self.client, self.host = host_client(self.root, runner=Runner())
        self.client.__enter__()
        self.runner = self.host._runner

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def post(self, path, body=None, status=200):
        response = self.client.post(path, json=body or {})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def lesson(self):
        turn = self.post('/api/lessons', {})['turn']
        self.host.wait(turn['id'], 5)
        settle(self.host)  # the next step is written ahead; let it finish before a test clears the prompts
        return next(p for p in self.runner.prompts if 'Current learner request' in p and 'Practice only' not in p)

    def test_chapter_overview_opens_the_first_section_and_later_sections_bridge(self):
        prompt = self.lesson()
        self.assertIn('## Chapter overview', prompt)
        self.assertIn('one core question', prompt)
        self.assertNotIn('English words', prompt)
        self.runner.prompts.clear()
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next-1'})
        prompt = self.lesson()
        self.assertNotIn('## Chapter overview', prompt)
        self.assertIn('connecting it to the previous section', prompt)

    def test_a_recap_belongs_to_the_chapter_and_starts_from_its_page_without_moving_the_position(self):
        self.post('/api/chapters/one/recap', {}, status=409)  # no section of the chapter has a lesson yet
        self.lesson()
        turn = self.post('/api/chapters/one/recap', {})['turn']
        self.host.wait(turn['id'], 5)
        self.assertEqual((turn['chapter_id'], turn['concept_id']), ('one', 'b'), 'anchored to the last section, owned by the chapter')
        recap = next(p for p in self.runner.prompts if '## Chapter recap' in p)
        self.assertIn('"not_studied_yet": ["Superposition"]', recap)
        state = self.client.get('/api/state').json()
        self.assertEqual(state['position']['concept_id'], 'a', 'a recap never moves the learner')
        self.assertEqual([j for j in state['practice']['jobs'] if j['concept_id'] == 'b'], [], 'a recap asks for no questions')

        # The recap anchored to b is not b's own lesson: b's first lesson still bridges from the previous section.
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next-1'})
        self.runner.prompts.clear()
        self.assertIn('connecting it to the previous section', self.lesson())
        self.post('/api/sections/next', {'concept_id': 'b', 'request_id': 'next-2'})
        self.assertEqual(self.client.get('/api/state').json()['position']['concept_id'], 'c')
        again = self.post('/api/chapters/one/recap', {})['turn']
        self.host.wait(again['id'], 5)
        self.assertEqual(self.client.get('/api/state').json()['position']['concept_id'], 'c', 'recapping an earlier chapter stays in this one')
        self.post('/api/chapters/two/recap', {}, status=409)
        self.post('/api/chapters/nope/recap', {}, status=404)

    def test_a_recap_waits_while_another_lesson_is_being_written(self):
        self.lesson()
        self.runner.gate = threading.Event()
        running = self.post('/api/lessons', {})['turn']
        try:
            self.assertEqual(self.post('/api/chapters/one/recap', {}, status=409)['code'], 'active_turn')
        finally:
            self.runner.gate.set()
        self.host.wait(running['id'], 5)
        self.post('/api/chapters/one/recap', {})

    def position(self):
        return self.client.get('/api/state').json()['position']

    def enter(self, concept_id, request_id, then_return=False, status=200):
        return self.post('/api/sections/enter', {'concept_id': concept_id, 'request_id': request_id, 'then_return': then_return}, status)

    def test_skipping_a_chapter_moves_on_and_marks_nothing(self):
        self.post('/api/chapters/two/skip', {'request_id': 'skip-0'}, status=409)
        self.post('/api/chapters/one/skip', {'request_id': 'skip-1'})
        state = self.client.get('/api/state').json()
        self.assertEqual(state['position']['concept_id'], 'c')
        self.assertNotIn('skipped', state)
        self.assertEqual(self.host.operation({'op': 'evidence.unresolved'})['deferred'], [], 'no section is deferred')
        self.enter('b', 'enter-1')
        self.assertEqual(self.position()['concept_id'], 'b')
        self.post('/api/chapters/two/skip', {'request_id': 'skip-2'}, status=409)

    def test_any_section_can_be_studied_from_here_earlier_or_later(self):
        self.lesson()
        self.enter('c', 'enter-1')
        self.assertEqual(self.position()['concept_id'], 'c')
        self.assertNotIn('return_to', self.position())
        self.enter('a', 'enter-2')  # studied before: it can be studied again
        self.assertEqual(self.position()['concept_id'], 'a')
        self.assertTrue(self.enter('a', 'enter-2')['replayed'], 'a retried move finds the learner there already')
        self.enter('nope', 'enter-3', status=404)
        self.assertEqual(self.host.operation({'op': 'evidence.unresolved'})['deferred'], [], 'no section is deferred')

    def test_a_detour_remembers_where_to_come_back_to(self):
        self.enter('c', 'detour', then_return=True)
        self.assertEqual((self.position()['concept_id'], self.position()['return_to']), ('c', 'a'))
        self.enter('b', 'further', then_return=True)
        self.assertEqual(self.position()['return_to'], 'a', 'a detour from a detour keeps the first section')
        self.enter('a', 'back')
        self.assertNotIn('return_to', self.position(), 'reaching it forgets it')

    def test_next_section_forgets_the_return_once_it_reaches_or_passes_it(self):
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next-1'})
        self.enter('a', 'again', then_return=True)  # back to an earlier section, to return to b
        self.assertEqual(self.position()['return_to'], 'b')
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next-2'})
        self.assertEqual(self.position()['concept_id'], 'b')
        self.assertNotIn('return_to', self.position())

        # Ahead of the section to come back to, moving on keeps it.
        self.enter('a', 'start-over')
        self.enter('b', 'ahead', then_return=True)
        self.post('/api/sections/next', {'concept_id': 'b', 'request_id': 'next-3'})
        self.assertEqual((self.position()['concept_id'], self.position()['return_to']), ('c', 'a'))

    def test_a_side_question_keeps_the_section_to_come_back_to(self):
        self.enter('c', 'detour', then_return=True)
        execute(self.root, {'op': 'interaction.record', 'id': 'q', 'role': 'user', 'text': 'Why?', 'concept_id': 'c'})
        execute(self.root, {'op': 'sidequestion.open', 'id': 'side', 'interaction_id': 'q', 'category': 'local', 'depth': 'short',
                            'rationale': 'r', 'strategy': 's'})
        execute(self.root, {'op': 'interaction.record', 'id': 'q-answer', 'role': 'assistant', 'text': 'Because.', 'concept_id': 'c'})
        execute(self.root, {'op': 'sidequestion.answer', 'id': 'side', 'answer_interaction_id': 'q-answer'})
        self.assertEqual(self.position()['return_to'], 'a')

if __name__ == '__main__':
    unittest.main()
