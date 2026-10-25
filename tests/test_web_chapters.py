import tempfile
import unittest
from pathlib import Path
from guided_learning.api import execute
from support import host_client


class Runner:
    """Captures each prompt and completes immediately; practice turns return no exercises."""

    def __init__(self):
        self.prompts = []

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
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

    def test_recap_is_offered_at_the_end_of_a_chapter_and_asks_for_retrieval_questions_separately(self):
        self.post('/api/chapters/one/recap', {}, status=409)
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next-1'})
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next-2'}, status=409)
        turn = self.post('/api/chapters/one/recap', {})['turn']
        self.host.wait(turn['id'], 5)
        self.assertTrue(any('## Chapter recap' in p for p in self.runner.prompts))
        jobs = self.client.get('/api/state').json()['practice']['jobs']
        self.assertEqual([(j['concept_id'], j['action'], j.get('purpose')) for j in jobs], [('b', 'generate', 'recap')])

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


if __name__ == '__main__':
    unittest.main()
