"""Review on request through the HTTP host (ADR 0014): review sets, recall and apply questions, the prepared set,
warm-ups and the chapter quiz."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from guided_learning.api import execute
from support import host_client, settle

DAY = 86400


def recall(tests, correct=0):
    return {'kind': 'recall', 'idea': 'global phase', 'question': 'Does a global phase change a probability?', 'tests_concept_ids': tests,
            'options': [{'text': 'No', 'explanation': 'Every probability is a squared magnitude.'}, {'text': 'Yes', 'explanation': 'A common misconception.'}],
            'correct': correct}


def apply(tests, **extra):
    return {'kind': 'apply', 'question': 'A new situation: why does the norm stay 1?', 'tests_concept_ids': tests, **extra}


class Runner:
    """Answers each kind of request the way the teacher would, and records the prompts."""

    def __init__(self):
        self.prompts = []
        self.outcome = 'passed'
        self.quiz_tests = [['a', 'b'], ['b']]  # the sections each new quiz question tests
        self.review = {'questions': [recall(['a']), apply(['a'])]}

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if 'Practice only (review set)' in prompt:
            text = json.dumps(self.review)
        elif 'Practice only (chapter quiz)' in prompt:
            text = json.dumps({'questions': [{'question': 'Connect states and superposition.', 'tests_concept_ids': self.quiz_tests[0]},
                                             {'question': 'Superposition in a new basis.', 'tests_concept_ids': self.quiz_tests[1]}]})
        elif 'Question and help history' in prompt:
            text = json.dumps({'feedback': 'Checked.', 'outcome': self.outcome})
        elif 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Normalize the state (1, 1).', 'origin': 'self_created', 'source_refs': []}]})
        else:
            text = '## Lesson\n\nText.\n<lesson-step>{"remaining": []}</lesson-step>'  # a one-step lesson leads to practice
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


class ReviewCourse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        execute(root, {'op': 'course.init', 'title': 'Quantum'})
        execute(root, {'op': 'curriculum.outline', 'chapters': [{'id': 'one', 'title': 'States'}, {'id': 'two', 'title': 'Measurement'}]})
        execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [{'id': 'a', 'title': 'What a state represents'}, {'id': 'b', 'title': 'Superposition'}]})
        execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': 'two', 'concepts': [{'id': 'c', 'title': 'Outcomes', 'prerequisites': ['a']}]})
        self.root = root
        self.runner = Runner()
        self.client, self.host = host_client(root, runner=self.runner)
        self.host.review.ahead = False  # the prepared set is written on purpose where a test wants one
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def post(self, path, body=None, status=200):
        response = self.client.post(path, json=body or {})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def state(self):
        return self.client.get('/api/state').json()

    def settle(self):
        settle(self.host)

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

    def ask(self, body=None, status=200):
        result = self.post('/api/review/sets', body or {}, status)
        self.settle()
        return result

    def review_prompt(self):
        return [p for p in self.runner.prompts if 'Practice only (review set)' in p][-1]

    def tasks(self, set_id):
        return [t for t in self.state()['review']['tasks'] if t['set_id'] == set_id]

    def listed(self, set_id):
        return next(s for s in self.state()['review']['sets'] if s['id'] == set_id)


class ReviewSets(ReviewCourse):
    def test_nothing_can_be_reviewed_before_anything_is_studied(self):
        self.assertEqual(self.state()['review']['reviewable'], 0)
        self.assertEqual(self.post('/api/review/sets', {}, 409)['code'], 'nothing_to_review')
        self.assertNotIn('count', json.dumps(self.state()['review']), 'nothing comes due: there is no schedule')

    def test_review_for_me_writes_recall_and_apply_questions_from_the_review_context(self):
        exercise = self.study('a')
        value = self.ask()['set']
        self.assertEqual(value['kind'], 'for_me')
        prompt = self.review_prompt()
        context = prompt.split('Sections the review may test')[1].split('\n')[0]
        self.assertIn('"id": "a"', context)
        self.assertNotIn('"id": "b"', context, 'b is not studied')
        self.assertIn('"days_since_practised": 0', context)
        self.assertIn('choose what to review', prompt)

        state = self.state()
        [first, second] = self.tasks(value['id'])
        self.assertEqual((first['kind'], second['kind']), ('recall', 'apply'))
        self.assertNotIn(first['id'], [t['id'] for t in state['practice']['tasks']], 'review questions are not section exercises')
        self.assertTrue(self.listed(value['id'])['open'])

        # A recall answer is instant and is not evidence.
        evidence = execute(self.root, {'op': 'evidence.view', 'concept_id': 'a'})['history']
        right = first['correct']
        answered = self.post(f'/api/review/tasks/{first["id"]}/answer', {'choice': right})['task']
        self.assertEqual((answered['answer']['choice'], answered['answer']['correct']), (right, True))
        self.assertEqual(self.post(f'/api/review/tasks/{first["id"]}/answer', {'choice': 1 - right})['task']['answer']['choice'], right, 'answered once')
        self.assertEqual(execute(self.root, {'op': 'evidence.view', 'concept_id': 'a'})['history'], evidence)
        self.post(f'/api/practice/tasks/{first["id"]}/assess', {'answer': 'No'}, 409)
        self.post(f'/api/practice/tasks/{second["id"]}/defer', {}, 409)
        self.post(f'/api/practice/tasks/{second["id"]}/skip', {}, 409)

        # An apply question is assessed like an exercise, and an unaided pass is a retest of its section.
        self.answer(second['id'])
        latest = execute(self.root, {'op': 'evidence.view', 'concept_id': 'a'})['latest_assessment']
        self.assertEqual(latest['kind'], 'retest_passed')
        first_job = next(j['id'] for j in self.host.practice.state()['jobs'] if j.get('task_id') == exercise['id'])
        self.assertEqual(latest['retest_of'], 'practice-evidence:' + first_job)
        listed = self.listed(value['id'])
        self.assertEqual((listed['open'], listed['answered'], listed['right']), (False, 2, 2))

        # The next set sees what was asked and how it went.
        self.ask({'request': 'phases again'})
        self.assertIn('"outcome": "right"', self.review_prompt().split('Earlier review and quiz questions')[1])

    def test_a_request_with_a_scope_tests_only_its_studied_sections(self):
        self.study('a')
        self.post('/api/sections/next', {'concept_id': 'a', 'request_id': 'next'})
        self.study('b')
        self.runner.review = {'note': 'Left out measurement: not studied yet.', 'questions': [apply(['b'])]}
        value = self.ask({'request': 'superposition and measurement', 'scope': {'concept_ids': ['b', 'c']}})['set']
        prompt = self.review_prompt()
        self.assertIn('superposition and measurement', prompt)
        context = prompt.split('Sections the review may test')[1].split('\n')[0]
        self.assertIn('"id": "b"', context)
        self.assertNotIn('"id": "a"', context)
        self.assertNotIn('"id": "c"', context, 'c is in scope but not studied')
        listed = self.listed(value['id'])
        self.assertEqual((listed['kind'], listed['note']), ('request', 'Left out measurement: not studied yet.'))

        # A question testing a section outside the set is refused, and nothing is written.
        self.runner.review = {'questions': [apply(['a'])]}
        refused = self.ask({'scope': {'chapter_ids': ['two']}}, 409)
        self.assertEqual(refused['code'], 'nothing_to_review', 'chapter two has nothing studied')
        value = self.ask({'scope': {'concept_ids': ['b']}})['set']
        self.assertEqual(self.tasks(value['id']), [])
        job = next(j for j in self.state()['review']['jobs'] if j['set_id'] == value['id'])
        self.assertIn('sections this review may test', job['error'])

    def test_a_malformed_recall_question_is_dropped_but_the_set_is_kept(self):
        self.study('a')
        broken = {**recall(['a']), 'options': [{'text': 'Only one'}]}
        parts = apply(['a'], parts=[{'label': '(a)', 'text': 'Recall.', 'concept_ids': ['a']}, {'label': '(b)', 'text': 'Apply.'}])
        self.runner.review = {'questions': [broken, parts]}
        value = self.ask()['set']
        [task] = self.tasks(value['id'])
        self.assertEqual(task['parts'][0]['concept_ids'], ['a'])
        self.runner.review = {'questions': [apply(['a'], parts=[{'text': 'Elsewhere.', 'concept_ids': ['b']}])]}
        value = self.ask({'request': 'again'})['set']
        self.assertEqual(self.tasks(value['id']), [], 'a part may test only sections its question tests')

    def test_a_set_can_be_closed_with_questions_unanswered(self):
        self.study('a')
        value = self.ask()['set']
        self.post(f'/api/review/sets/{value["id"]}/close')
        listed = self.listed(value['id'])
        self.assertFalse(listed['open'])
        self.assertEqual(listed['answered'], 0)

    def test_review_for_me_uses_the_prepared_set_at_once(self):
        self.study('a')
        self.assertIsNone(self.host.review.prepare(), 'nothing is prepared for a learner who never asked for a review')
        self.ask()
        self.host.review.prepare()
        self.settle()
        prepared = next(s for s in execute(self.root, {'op': 'review.sets'})['sets'] if s.get('prepared'))
        self.assertNotIn(prepared['id'], [s['id'] for s in self.state()['review']['sets']], 'hidden until asked for')
        self.assertNotIn(prepared['id'], {t['set_id'] for t in self.state()['review']['tasks']})
        self.assertIsNone(self.host.review.prepare(), 'one prepared set at a time')
        result = self.post('/api/review/sets', {})
        self.assertEqual(result['set']['id'], prepared['id'])
        self.assertNotIn('turn', result, 'nothing to wait for')
        self.assertEqual(len(self.tasks(prepared['id'])), 2)
        # A request with words always writes a new set.
        self.host.review.prepare()
        self.settle()
        self.assertNotEqual(self.ask({'request': 'phases'})['set']['id'], prepared['id'])

    def test_a_warm_up_is_offered_once_on_a_section_whose_prerequisite_went_stale(self):
        self.study('a')
        self.assertEqual(self.state()['review']['warm_ups'], {}, 'a was just practised')
        self.host.review.clock = lambda: time.time() + 8 * DAY
        self.assertEqual(self.state()['review']['warm_ups'], {'c': ['a']})
        self.runner.review = {'questions': [recall(['a'])]}
        value = self.ask({'warm_up_for': 'c'})['set']
        self.assertEqual((value['kind'], value['concept_id']), ('warm_up', 'c'))
        self.assertIn('warm-up', self.review_prompt())
        self.assertEqual(self.state()['review']['warm_ups'], {}, 'offered once')

    def test_a_dismissed_warm_up_is_not_offered_again(self):
        self.study('a')
        self.host.review.clock = lambda: time.time() + 8 * DAY
        self.post('/api/review/warm-ups/c/dismiss')
        self.assertEqual(self.state()['review']['warm_ups'], {})


class ChapterQuiz(ReviewCourse):
    def test_new_quiz_questions_test_only_studied_sections(self):
        self.study('a')
        self.post('/api/chapters/one/quiz')
        self.settle()
        prompt = next(p for p in self.runner.prompts if 'Practice only (chapter quiz)' in p)
        sections = prompt.split('Sections (data): ')[1].split('\n')[0]
        self.assertIn('"id": "a"', sections)
        self.assertNotIn('"id": "b"', sections, 'b has no lesson yet, so a new question may not test it')
        job = next(j for j in self.state()['practice']['jobs'] if j.get('purpose') == 'chapter_quiz')
        self.assertIn('studied', job.get('error', ''), 'the canned reply tests b, which is refused')

    def test_a_chapter_quiz_is_a_review_set_mixing_earlier_exercises_with_new_questions(self):
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
        self.assertIn('Earlier exercises already in this quiz (data): [{"section": "What a state represents"', prompt)

        quiz = [t for t in state['practice']['tasks'] if t['origin'] == 'chapter_quiz']
        self.assertEqual([(t.get('from_task_id'), t['tests_concept_ids']) for t in quiz],
                         [(first['id'], ['a']), (second['id'], ['b']), (None, ['a', 'b']), (None, ['b'])],
                         'earlier exercises first, in route order, then the new questions')
        quiz_id = quiz[0]['quiz_id']
        self.assertEqual({(t['chapter_id'], t['concept_id'], t['quiz_id'], t['set_id']) for t in quiz}, {('one', 'b', quiz_id, quiz_id)})
        self.assertEqual({t['id']: t for t in state['practice']['tasks'] if t['id'] in originals}, originals, 'the originals are untouched')
        self.assertEqual(self.post('/api/practice/generate', {'concept_id': 'b'})['tasks'], [originals[second['id']]],
                         "quiz questions anchored to b are not b's exercises")
        listed = self.listed(quiz_id)
        self.assertEqual((listed['kind'], listed['chapter_id'], listed['open']), ('chapter_quiz', 'one', True))
        self.post('/api/chapters/one/quiz', {}, status=409)  # the current quiz is still open
        self.post(f'/api/practice/tasks/{quiz[0]["id"]}/defer', {}, status=409)

        self.answer(quiz[0]['id'])
        latest = execute(self.root, {'op': 'evidence.view', 'concept_id': 'a'})['latest_assessment']
        self.assertEqual(latest['kind'], 'retest_passed', 'an unaided pass of an earlier exercise is a retest of its section')
        self.assertEqual(self.listed(quiz_id)['answered'], 1)
        for task in quiz[1:]:
            self.answer(task['id'], 'needs_work')
        self.assertEqual((self.listed(quiz_id)['answered'], self.listed(quiz_id)['right']), (4, 1))
        self.post('/api/chapters/one/quiz')
        self.settle()
        self.assertEqual(len({t['quiz_id'] for t in self.state()['practice']['tasks'] if t['origin'] == 'chapter_quiz'}), 2,
                         'once every question is answered the quiz can be taken again')


if __name__ == '__main__':
    unittest.main()
