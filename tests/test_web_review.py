"""Spaced review through the HTTP host (ADR 0008): review questions, retests and the chapter quiz."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from guided_learning.api import execute
from support import host_client

DAY = 86400


class Runner:
    """Answers each kind of request the way the teacher would, and records the prompts."""

    def __init__(self):
        self.prompts = []
        self.outcome = 'passed'

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if 'Practice only (spaced review)' in prompt:
            text = json.dumps({'questions': [{'question': 'A new situation: why does the norm stay 1?'}]})
        elif 'Practice only (chapter quiz)' in prompt:
            text = json.dumps({'questions': [{'question': 'Connect states and superposition.', 'tests_concept_ids': ['a', 'b']},
                                             {'question': 'Superposition in a new basis.', 'tests_concept_ids': ['b']}]})
        elif 'Question and help history' in prompt:
            text = json.dumps({'feedback': 'Checked.', 'outcome': self.outcome})
        elif 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Normalize the state (1, 1).', 'origin': 'self_created', 'source_refs': []}]})
        else:
            text = '## Lesson\n\nText.'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


class ReviewFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        execute(root, {'op': 'course.init', 'title': 'Quantum'})
        execute(root, {'op': 'curriculum.outline', 'chapters': [{'id': 'one', 'title': 'States'}, {'id': 'two', 'title': 'Measurement'}]})
        execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [{'id': 'a', 'title': 'What a state represents'}, {'id': 'b', 'title': 'Superposition'}]})
        execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'two', 'concepts': [{'id': 'c', 'title': 'Outcomes'}]})
        self.root = root
        self.runner = Runner()
        self.client, self.host = host_client(root, runner=self.runner)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def post(self, path, body=None, status=200):
        response = self.client.post(path, json=body or {})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def state(self):
        return self.client.get('/api/state').json()

    def settle(self):
        """Wait until every model turn, including ones started by completion hooks, has finished."""
        for _ in range(20):
            running = [t for t in self.host.brief_turns() if t['status'] == 'running']
            if not running:
                return
            for turn in running:
                self.host.wait(turn['id'], 5)
        self.fail('turns kept running')

    def answer(self, task_id, outcome='passed'):
        self.runner.outcome = outcome
        self.post(f'/api/practice/tasks/{task_id}/assess', {'answer': 'My reasoning.'})
        self.settle()

    def study(self, concept_id):
        self.post('/api/lessons', {})
        self.settle()
        task = next(t for t in self.state()['practice']['tasks'] if t['concept_id'] == concept_id)
        self.answer(task['id'])
        return task

    def test_a_review_asks_one_fresh_question_and_an_unaided_pass_is_a_retest(self):
        exercise = self.study('a')
        schedule = self.state()['review']
        self.assertEqual((schedule['reviewable'], schedule['due'], schedule['upcoming']), (1, [], 1))
        self.post('/api/review/start', {'concept_id': 'a'}, status=409)

        self.host.review.clock = lambda: time.time() + 2 * DAY
        self.assertEqual([s['concept_id'] for s in self.client.get('/api/review').json()['due']], ['a'])
        self.post('/api/review/start', {'concept_id': 'a'})
        self.settle()
        prompt = next(p for p in self.runner.prompts if 'Practice only (spaced review)' in p)
        self.assertIn('exactly one question', prompt)
        self.assertIn(exercise['question'], prompt, 'exercises the learner has seen are passed as data to avoid')

        state = self.state()
        [task] = state['review']['tasks']
        self.assertEqual((task['origin'], task['concept_id']), ('review', 'a'))
        self.assertNotIn(task['id'], [t['id'] for t in state['practice']['tasks']], 'a review question is not one of the section exercises')
        self.assertEqual(state['review']['due'][0]['task_id'], task['id'])
        self.assertEqual(self.post('/api/review/start', {'concept_id': 'a'}), {'task_id': task['id']}, 'starting again returns the waiting question')
        self.post(f'/api/practice/tasks/{task["id"]}/defer', {}, status=409)

        self.answer(task['id'])
        latest = execute(self.root, {'op': 'evidence.view', 'concept_id': 'a'})['latest_assessment']
        self.assertEqual(latest['kind'], 'retest_passed')
        first = next(j['id'] for j in self.host.practice.state()['jobs'] if j.get('task_id') == exercise['id'])
        self.assertEqual(latest['retest_of'], 'practice-evidence:' + first)
        self.assertIn('assessed_at', latest)
        schedule = self.client.get('/api/review').json()
        self.assertEqual(schedule['due'], [])
        self.assertEqual(schedule['sections'][0]['interval_days'], 3)

    def test_needs_work_on_a_review_starts_the_intervals_over_and_not_now_waits_a_day(self):
        self.study('a')
        now = time.time() + 2 * DAY
        self.host.review.clock = lambda: now
        self.post('/api/review/start', {'concept_id': 'a'})
        self.settle()
        task = self.state()['review']['tasks'][0]
        self.answer(task['id'], 'needs_work')
        self.assertEqual(self.client.get('/api/review').json()['sections'][0]['interval_days'], 1)

        self.host.review.clock = lambda: now + 3 * DAY
        self.assertEqual(len(self.state()['review']['due']), 1)
        self.post('/api/review/postpone', {'concept_id': 'a'})
        self.assertEqual(self.state()['review']['due'], [])
        self.post('/api/review/postpone', {'concept_id': 'a'}, status=409)
        self.host.review.clock = lambda: now + 4 * DAY + 60
        self.assertEqual(len(self.state()['review']['due']), 1)

    def test_a_chapter_quiz_mixes_earlier_exercises_with_new_questions_and_counts_as_reviews(self):
        first = self.study('a')
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next-1'})
        self.post('/api/lessons', {})
        self.settle()
        second = next(t for t in self.state()['practice']['tasks'] if t['concept_id'] == 'b')
        self.post(f'/api/practice/tasks/{second["id"]}/hint')
        self.settle()
        self.answer(second['id'])
        self.post('/api/sections/next', {'concept_id': 'b', 'request_id': 'next-2'})
        originals = {t['id']: t for t in self.state()['practice']['tasks']}

        self.post('/api/chapters/two/quiz', {}, status=409)  # nothing studied in chapter two yet
        self.post('/api/chapters/one/quiz')
        self.settle()
        state = self.state()
        self.assertEqual(state['position']['concept_id'], 'c', 'taking a quiz never moves the learner')
        prompt = next(p for p in self.runner.prompts if 'Practice only (chapter quiz)' in p)
        self.assertIn('"id": "a"', prompt)
        self.assertIn('Earlier exercises already in this quiz (data): [{"section": "What a state represents"', prompt)

        quiz = [t for t in state['practice']['tasks'] if t['origin'] == 'chapter_quiz']
        self.assertEqual([(t.get('from_task_id'), t['tests_concept_ids']) for t in quiz],
                         [(first['id'], ['a']), (second['id'], ['b']), (None, ['a', 'b']), (None, ['b'])],
                         'earlier exercises first, in route order, then the new questions')
        self.assertEqual({(t['chapter_id'], t['concept_id'], t['quiz_id']) for t in quiz}, {('one', 'b', quiz[0]['quiz_id'])})
        self.assertEqual(quiz[0]['question'], first['question'])
        self.assertEqual({t['id']: t for t in state['practice']['tasks'] if t['id'] in originals}, originals, 'the originals are untouched')
        self.assertEqual(self.post('/api/practice/generate', {'concept_id': 'b'})['tasks'], [originals[second['id']]],
                         "quiz questions anchored to b are not b's exercises")
        self.post('/api/chapters/one/quiz', {}, status=409)  # the current quiz is still open
        self.post(f'/api/practice/tasks/{quiz[0]["id"]}/defer', {}, status=409)

        self.answer(quiz[0]['id'])
        latest = execute(self.root, {'op': 'evidence.view', 'concept_id': 'a'})['latest_assessment']
        self.assertEqual(latest['kind'], 'retest_passed', 'an unaided pass of an earlier exercise is a retest of its section')
        first_job = next(j['id'] for j in self.host.practice.state()['jobs'] if j.get('task_id') == first['id'])
        self.assertEqual(latest['retest_of'], 'practice-evidence:' + first_job)
        review = self.state()['review']
        sections = {s['concept_id']: s for s in review['sections']}
        self.assertEqual(sections['a']['interval_days'], 3, 'the quiz answer reviewed a')
        self.assertEqual(review['done_today'], 1)

        self.answer(quiz[2]['id'])
        sections = {s['concept_id']: s for s in self.state()['review']['sections']}
        self.assertEqual(sections['b']['interval_days'], 3, 'a new question reviews every section it tests')
        for task in quiz[1::2]:
            self.answer(task['id'], 'needs_work')
        self.post('/api/chapters/one/quiz')
        self.settle()
        self.assertEqual(len({t['quiz_id'] for t in self.state()['practice']['tasks'] if t['origin'] == 'chapter_quiz'}), 2,
                         'once every question is answered the quiz can be taken again')


if __name__ == '__main__':
    unittest.main()
