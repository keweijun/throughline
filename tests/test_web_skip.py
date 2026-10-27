"""Skipping a section exercise (ADR 0011): it is closed, records nothing, and no quiz or reminder brings it back."""
import tempfile
import time
import unittest
from pathlib import Path

from guided_learning.api import execute
from support import host_client
from test_web_review import DAY, Runner


class SkipFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        execute(root, {'op': 'course.init', 'title': 'Quantum'})
        execute(root, {'op': 'curriculum.outline', 'chapters': [{'id': 'one', 'title': 'States'}]})
        execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [{'id': 'a', 'title': 'What a state represents'}, {'id': 'b', 'title': 'Superposition'}]})
        self.root = root
        self.runner = Runner()
        self.client, self.host = host_client(root, runner=self.runner)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def post(self, path, body=None, status=200):
        response = self.client.post(path, json=body or {})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def task(self, task_id):
        return next(t for t in self.host.practice.state()['tasks'] if t['id'] == task_id)

    def settle(self):
        for _ in range(20):
            running = [t for t in self.host.brief_turns() if t['status'] == 'running']
            if not running:
                return
            for turn in running:
                self.host.wait(turn['id'], 5)
        self.fail('turns kept running')

    def exercise(self):
        self.post('/api/lessons', {})
        self.settle()
        return next(t for t in self.host.practice.state()['tasks'] if t['concept_id'] == 'a')

    def records(self):
        return (execute(self.root, {'op': 'evidence.unresolved'})['deferred'], execute(self.root, {'op': 'evidence.view', 'concept_id': 'a'}))

    def test_skip_with_a_reason_closes_the_exercise_and_records_no_evidence(self):
        task = self.exercise()
        before = self.records()
        result = self.post(f'/api/practice/tasks/{task["id"]}/skip', {'reason': 'too_easy'})
        self.assertEqual((result['task']['status'], result['task']['skip_reason']), ('skipped', 'too_easy'))
        self.assertEqual(self.task(task['id'])['status'], 'skipped')
        self.assertEqual(self.records(), before, 'a skip records no outcome, evidence or deferral')

    def test_skip_without_a_reason(self):
        task = self.exercise()
        self.post(f'/api/practice/tasks/{task["id"]}/skip', {'reason': 'not_relevant'})
        result = self.post(f'/api/practice/tasks/{task["id"]}/skip', {})
        self.assertEqual(result['task']['status'], 'skipped')
        self.assertNotIn('skip_reason', result['task'], 'skipping again without a reason drops the earlier one')

    def test_a_skipped_exercise_is_not_reminded_in_the_chapter_recap(self):
        task = self.exercise()
        self.post(f'/api/practice/tasks/{task["id"]}/defer')
        chapter = self.host.navigation.chapter('one')
        self.assertEqual(len(self.host.navigation._recap_data(chapter)[1]), 1)
        self.post(f'/api/practice/tasks/{task["id"]}/skip', {'reason': 'too_tedious'})
        self.assertEqual(self.host.navigation._recap_data(chapter)[1], [])

    def test_an_unknown_reason_is_refused(self):
        task = self.exercise()
        self.post(f'/api/practice/tasks/{task["id"]}/skip', {'reason': 'boring'}, status=409)
        self.assertEqual(self.task(task['id'])['status'], 'pending')

    def test_review_and_quiz_questions_cannot_be_skipped(self):
        task = self.exercise()
        self.runner.outcome = 'passed'
        self.post(f'/api/practice/tasks/{task["id"]}/assess', {'answer': 'My reasoning.'})
        self.settle()
        self.host.review.clock = lambda: time.time() + 2 * DAY
        self.post('/api/review/start', {'concept_id': 'a'})
        self.settle()
        review = next(t for t in self.host.practice.state()['tasks'] if t['origin'] == 'review')
        self.post(f'/api/practice/tasks/{review["id"]}/skip', {}, status=409)
        self.post('/api/chapters/one/quiz')
        self.settle()
        quiz = next(t for t in self.host.practice.state()['tasks'] if t['origin'] == 'chapter_quiz')
        self.post(f'/api/practice/tasks/{quiz["id"]}/skip', {}, status=409)
        self.assertEqual(self.task(quiz['id'])['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
