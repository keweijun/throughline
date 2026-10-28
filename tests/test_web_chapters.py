import tempfile
import threading
import unittest
from pathlib import Path
from guided_learning.api import execute
from support import host_client, settle


class Runner:
    """Captures each prompt and completes immediately, or once `gate` opens; practice turns return no exercises."""

    def __init__(self):
        self.prompts = []
        self.gate = None

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if self.gate:
            self.gate.wait(5)
        emit({'kind': 'final', 'text': '{"questions": []}' if 'Practice only' in prompt else 'Lesson text'})
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

    def test_skipping_a_chapter_defers_its_sections_until_the_learner_returns(self):
        self.post('/api/chapters/two/skip', {'request_id': 'skip-0'}, status=409)
        self.post('/api/chapters/one/skip', {'request_id': 'skip-1'})
        state = self.client.get('/api/state').json()
        self.assertEqual(state['position']['concept_id'], 'c')
        self.assertEqual({d['concept_id'] for d in state['skipped']}, {'a', 'b'})
        self.post('/api/sections/enter', {'concept_id': 'c', 'request_id': 'enter-0'}, status=409)
        self.post('/api/sections/enter', {'concept_id': 'b', 'request_id': 'enter-1'})
        self.lesson()
        self.assertEqual([d['concept_id'] for d in self.client.get('/api/state').json()['skipped']], ['a'])
        self.post('/api/chapters/two/skip', {'request_id': 'skip-2'}, status=409)

    def test_jumping_to_a_later_section_skips_the_unstudied_ones_passed_over(self):
        self.lesson()  # a is studied, so jumping past it does not mark it skipped
        self.post('/api/sections/jump', {'concept_id': 'c', 'request_id': 'jump-1'})
        state = self.client.get('/api/state').json()
        self.assertEqual(state['position']['concept_id'], 'c')
        self.assertEqual([(d['concept_id'], d['target_concept_id'], d['section_id']) for d in state['skipped']], [('b', 'c', 'one')])
        # A retry of the same jump lands where the first did and skips nothing more.
        self.post('/api/sections/jump', {'concept_id': 'c', 'request_id': 'jump-1'})
        self.assertEqual(len(self.client.get('/api/state').json()['skipped']), 1)
        self.assertEqual(self.post('/api/sections/jump', {'concept_id': 'a', 'request_id': 'jump-2'}, status=409)['code'], 'not_ahead')
        self.post('/api/sections/jump', {'concept_id': 'nope', 'request_id': 'jump-3'}, status=404)
        # A section jumped past is studied like one skipped with its chapter, which clears the mark.
        self.post('/api/sections/enter', {'concept_id': 'b', 'request_id': 'enter-1'})
        self.lesson()
        self.assertEqual(self.client.get('/api/state').json()['skipped'], [])

    def test_jumping_from_an_unstarted_section_skips_it_too(self):
        self.post('/api/sections/jump', {'concept_id': 'b', 'request_id': 'jump-1'})
        state = self.client.get('/api/state').json()
        self.assertEqual(state['position']['concept_id'], 'b')
        self.assertEqual([d['concept_id'] for d in state['skipped']], ['a'])


if __name__ == '__main__':
    unittest.main()
