"""Drill sessions through the HTTP host (ADR 0025): a fast teacher drills the learner over the Review place's scope,
its questions are review questions answered and assessed as before, and a chapter drill and a warm-up are sessions."""
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
    """Answers each kind of request the way the teacher would, and records the prompts and whether a drill's ran on the
    small model (the host passes it a runner per turn)."""

    def __init__(self):
        self.prompts = []
        self.outcome = 'passed'
        self.drill = {'questions': [recall(['a']), apply(['a'])]}
        self.reply = 'Here are two quick ones.'

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if 'drilling the learner' in prompt:
            text = self.reply + ('\n<drill-questions>' + json.dumps(self.drill) + '</drill-questions>' if self.drill else '')
            if 'cheat sheet' in prompt.rsplit('The learner now says:', 1)[-1]:
                text = 'Studio can make that for you.\n<studio-request>{"label": "A cheat sheet for States", "request": "Make me a one-page cheat sheet for the chapter States."}</studio-request>'
        elif 'Question and help history' in prompt:
            text = json.dumps({'feedback': 'Checked.', 'outcome': self.outcome})
        elif 'Practice only' in prompt:
            text = json.dumps({'questions': [{'question': 'Normalize the state (1, 1).', 'origin': 'self_created', 'source_refs': []}]})
        else:
            text = '## Lesson\n\nText.\n<lesson-step>{"remaining": []}</lesson-step>'  # a one-step lesson leads to practice
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


class DrillCourse(unittest.TestCase):
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
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        # Every turn asks the settings for its runner, so the test sees which ran on the small model.
        self.small = []
        self.host._runner = None
        self.host.settings.runner = self._runner_for

    def _runner_for(self, small=False, fast=False):
        self.small.append(small)
        self.fast = getattr(self, 'fast', []) + [fast]
        return self.runner

    def post(self, path, body=None, status=200):
        response = self.client.post(path, json=body or {})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def state(self):
        return self.client.get('/api/state').json()

    def answer(self, task_id, outcome='passed'):
        self.runner.outcome = outcome
        self.post(f'/api/practice/tasks/{task_id}/assess', {'answer': 'My reasoning.'})
        settle(self.host)

    def study(self, concept_id):
        self.post('/api/lessons', {})
        settle(self.host)
        task = next(t for t in self.state()['practice']['tasks'] if t['concept_id'] == concept_id)
        self.answer(task['id'])
        return task

    def drill(self, body=None, status=200):
        result = self.post('/api/drills', body or {}, status)
        settle(self.host)
        return result

    def session(self, identifier):
        return next(s for s in self.state()['drills'] if s['id'] == identifier)

    def miss(self, task_id):
        """Answer a recall question wrongly; its options are shuffled when it is saved."""
        task = next(t for t in self.state()['review']['tasks'] if t['id'] == task_id)
        self.post(f'/api/review/tasks/{task_id}/answer', {'choice': 1 - task['correct']})

    def drill_prompt(self):
        return [p for p in self.runner.prompts if 'drilling the learner' in p][-1]


class Drills(DrillCourse):
    def test_nothing_to_drill_before_anything_is_studied(self):
        self.assertEqual(self.post('/api/drills', {}, 409)['code'], 'nothing_to_review')
        self.assertEqual(self.state()['drills'], [])

    def test_a_session_asks_recall_and_apply_questions_on_the_small_model_and_its_answers_count(self):
        self.study('a')
        self.small.clear()
        session = self.drill({'id': 's1'})['session']
        turn = session['turn_ids'][0]
        listed = self.session('s1')
        self.assertEqual((listed['kind'], listed['sections'], listed['task_ids']), ('drill', ['a'], [turn + ':0', turn + ':1']))
        self.assertTrue(self.small[-1], 'a drill turn runs on the small model')
        prompt = self.drill_prompt()
        self.assertIn('"days_since_practised": 0', prompt, 'the review context reaches the teacher')
        self.assertIn('The learner now says:\nDrill me.', prompt)
        shown = next(t for t in self.state()['turns'] if t['id'] == turn)
        self.assertIn('Here are two quick ones.', shown['text'])
        tasks = {t['id']: t for t in self.state()['review']['tasks']}
        self.assertEqual((tasks[turn + ':0']['kind'], tasks[turn + ':0']['session_id']), ('recall', 's1'))
        self.miss(f'{turn}:0')
        self.small.clear()
        self.answer(turn + ':1')
        self.assertTrue(all(self.small), 'its written answers are assessed on the small model too')
        assessed = next(t for t in self.state()['review']['tasks'] if t['id'] == turn + ':1')
        self.assertEqual(assessed['history'][-1]['kind'], 'retest_passed', 'an unaided pass is evidence, a retest of the section')
        self.assertEqual([m['id'] for m in self.state()['mistakes']], [f'recall:{turn}:0'], 'a miss reaches the mistakes book')

    def test_the_conversation_goes_on_with_what_was_asked_and_how_it_went(self):
        self.study('a')
        first = self.drill({'id': 's1'})['session']['turn_ids'][0]
        self.miss(f'{first}:0')
        self.runner.drill = {'questions': [recall(['a'])]}
        self.post('/api/drills/s1/messages', {'message': 'Only phases, please'})
        settle(self.host)
        prompt = self.drill_prompt()
        self.assertIn('Only phases, please', prompt)
        self.assertIn('"outcome": "missed"', prompt, 'the teacher sees how the questions went')
        self.assertEqual(len(self.session('s1')['turn_ids']), 2)
        self.runner.drill = None
        self.runner.reply = 'Done for today. Well done.'
        self.post('/api/drills/s1/messages', {'message': "That's enough"})
        settle(self.host)
        self.assertEqual(len(self.session('s1')['task_ids']), 3, 'a reply may ask nothing')

    def test_a_scope_narrows_the_questions_and_one_reaching_beyond_it_is_refused(self):
        self.study('a')
        self.runner.drill = {'questions': [apply(['c'])]}
        session = self.drill({'id': 's1', 'scope': {'chapter_ids': ['one']}})['session']
        self.assertEqual(self.session('s1')['task_ids'], [], 'a question testing a section out of scope is not asked')
        self.assertIn('"id": "a"', self.drill_prompt())
        self.assertEqual(session['scope'], {'chapter_ids': ['one']})
        self.assertEqual(self.post('/api/drills', {'scope': {'chapter_ids': ['two']}}, 409)['code'], 'nothing_to_review')

    def test_one_turn_at_a_time(self):
        self.study('a')
        self.drill({'id': 's1'})
        hold = __import__('threading').Event()
        original = self.runner.run

        def slow(prompt, cwd, emit, cancel):
            hold.wait(5)
            original(prompt, cwd, emit, cancel)
        self.runner.run = slow
        self.post('/api/drills/s1/messages', {})
        try:
            self.assertEqual(self.post('/api/drills/s1/messages', {}, 409)['code'], 'drill_busy')
        finally:
            hold.set()
        settle(self.host)

    def test_a_chapter_drill_and_a_warm_up_are_sessions_with_their_own_scope(self):
        self.study('a')
        chapter = self.drill({'id': 'ch', 'kind': 'chapter', 'chapter_id': 'one'})['session']
        self.assertEqual((chapter['kind'], chapter['chapter_id']), ('chapter', 'one'))
        self.assertIn('earlier exercises asked again', self.drill_prompt())
        self.assertEqual(self.state()['review']['warm_ups'], {}, 'a was just practised')
        self.host.review.clock = lambda: time.time() + 8 * DAY
        self.assertEqual(self.state()['review']['warm_ups'], {'c': ['a']})
        self.runner.drill = {'questions': [recall(['a'])]}
        warm = self.drill({'id': 'w', 'kind': 'warm_up', 'concept_id': 'c'})['session']
        self.assertEqual(self.session(warm['id'])['sections'], ['a'])
        self.assertIn('warm-up before the learner starts the section "Outcomes"', self.drill_prompt())
        self.assertEqual(self.state()['review']['warm_ups'], {}, 'offered once')

    def test_a_dismissed_warm_up_is_not_offered_again(self):
        self.study('a')
        self.host.review.clock = lambda: time.time() + 8 * DAY
        self.post('/api/review/warm-ups/c/dismiss')
        self.assertEqual(self.state()['review']['warm_ups'], {})

    def test_review_sets_and_chapter_quizzes_are_no_longer_started(self):
        self.study('a')
        self.post('/api/review/sets', {}, 404)
        self.post('/api/chapters/one/quiz', {}, 404)

    def test_a_reply_offers_studio_what_it_cannot_do_and_the_hand_off_is_kept(self):
        self.study('a')
        self.drill({'id': 's1'})
        self.post('/api/drills/s1/messages', {'message': 'Can you make me a cheat sheet?'})
        settle(self.host)
        session = self.session('s1')
        turn = session['turn_ids'][-1]
        self.assertEqual(session['handoffs'][turn], {'label': 'A cheat sheet for States', 'request': 'Make me a one-page cheat sheet for the chapter States.'})
        self.assertIn('<studio-request>', self.drill_prompt(), 'the teacher is told how to offer Studio')
        shown = next(t for t in self.state()['turns'] if t['id'] == turn)
        self.assertIn('Studio can make that for you.', shown['text'])
        sent = self.post('/api/handoffs', {'id': 'drill:' + turn, 'place': {'kind': 'drill', 'session': 's1', 'turn': turn},
                                           'label': 'A cheat sheet for States', 'request': 'Make me a one-page cheat sheet.', 'thread_id': 'thread-1'})['handoff']
        self.assertEqual(sent['thread_id'], 'thread-1')
        again = self.post('/api/handoffs', {'id': 'drill:' + turn, 'place': {'kind': 'drill'}, 'label': 'x', 'request': 'y', 'thread_id': 'thread-2'})['handoff']
        self.assertEqual(again['thread_id'], 'thread-1', 'a hand-off is recorded once')
        self.assertEqual([h['id'] for h in self.state()['handoffs']], ['drill:' + turn])
        self.post('/api/drills/s1/messages', {'message': 'Thanks'})
        settle(self.host)
        self.assertIn('"offered_to_studio": "A cheat sheet for States", "sent_to_studio": true', self.drill_prompt())
        self.post('/api/handoffs', {'id': 'x', 'place': {'kind': 'elsewhere'}, 'label': 'x', 'request': 'y', 'thread_id': 't'}, 409)

    def test_a_way_to_review_shapes_the_session(self):
        self.study('a')
        execute(self.root, {'op': 'memory.save', 'id': 'd1', 'kind': 'difficulty', 'text': 'Global and relative phase', 'concept_id': 'a'})
        for way, said in (('explain', 'explain it back'), ('oral', 'an oral quiz'), ('confusable', 'tells confusable ideas apart')):
            session = self.drill({'way': way})['session']
            self.assertEqual(session['way'], way)
            self.assertIn(said, self.drill_prompt())
        self.assertIn('Global and relative phase', self.drill_prompt(), 'difficulties reach the teacher')
        self.assertNotIn('way', self.drill({})['session'], 'quick questions is the default')
        self.post('/api/drills', {'way': 'sing'}, 400)

    def test_drill_questions_cannot_be_skipped(self):
        self.study('a')
        turn = self.drill({'id': 's1'})['session']['turn_ids'][0]
        self.post(f'/api/practice/tasks/{turn}:1/skip', {}, status=409)


if __name__ == '__main__':
    unittest.main()
