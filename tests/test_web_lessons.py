"""Stepped lessons (ADR 0009): a section's first lesson is taught in lesson steps, one turn each."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from guided_learning.api import execute
from support import host_client

OVERVIEW = {'core_problem': 'Why do paths cancel?', 'steps': ['Amplitudes', 'Adding amplitudes', 'Probability'],
            'prior': 'Waves', 'next': 'States', 'target_ability': 'Predict interference'}


CHECK = {'idea': 'Amplitudes add before squaring', 'question': 'Two paths each give amplitude 1/2. What is P?',
         'options': [{'text': 'P = 1', 'explanation': 'Add the amplitudes, then square: |1/2 + 1/2|^2 = 1.'},
                     {'text': 'P = 1/2', 'explanation': 'This adds the probabilities; amplitudes add first.'},
                     {'text': 'P = 0', 'explanation': 'Paths cancel only when the amplitudes have opposite signs.'}],
         'correct': 0}


def step_reply(text, remaining=None, title=None, check=None):
    data = {'check': check} if check else {}
    if title:
        data['title'] = title
    if remaining is not None:
        data['remaining'] = remaining
    return text + '\n<lesson-step>' + json.dumps(data) + '</lesson-step>'


class Runner:
    """Answers lesson steps from a queue of replies; practice requests get one exercise."""
    def __init__(self):
        self.replies, self.prompts, self.hold = [], [], threading.Event()

    def run(self, prompt, cwd, emit, cancel):
        if 'Practice only' in prompt:
            emit({'kind': 'final', 'text': '{"questions":[{"question":"Find P.","origin":"self_created","source_refs":[]}]}'})
            emit({'kind': 'complete'})
            return
        if 'Internal preparation task' in prompt:
            return
        self.prompts.append(prompt)
        if self.hold.is_set():
            cancel.wait(5)
            return
        emit({'kind': 'final', 'text': self.replies.pop(0) if self.replies else 'Plain lesson.'})
        emit({'kind': 'complete'})


class SteppedLessons(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        execute(self.root, {'op': 'course.init', 'title': 'Quantum'})
        execute(self.root, {'op': 'curriculum.save', 'route': ['wave', 'state'], 'coverage': [],
                            'concepts': [{'id': 'wave', 'title': 'Wave', 'overview': OVERVIEW}, {'id': 'state', 'title': 'State', 'prerequisites': ['wave']}]})
        self.runner = Runner()
        self.client, self.host = host_client(self.root, runner=self.runner)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def post(self, path, body=None, status=200):
        response = self.client.post(path, json=body or {})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def finish(self, turn_id):
        self.assertEqual(self.host.wait(turn_id, 5)['status'], 'completed')
        deadline = time.monotonic() + 5
        while any(t['status'] == 'running' and t['channel'] == 'practice' for t in self.host.brief_turns()) and time.monotonic() < deadline:
            time.sleep(.02)

    def state(self):
        return self.client.get('/api/state').json()

    def lesson(self, identifier='one'):
        return next(item for item in self.state()['lessons'] if item['id'] == identifier)

    def generated(self):
        return [j for j in self.state()['practice']['jobs'] if j['action'] == 'generate']

    def test_first_lesson_teaches_step_one_with_a_plan_and_continue_teaches_the_rest(self):
        self.runner.replies = [
            step_reply('Step one text.', [{'title': 'Complex numbers refresher', 'added': True}, {'title': 'Adding amplitudes', 'added': False}, {'title': 'Probability'}], title='Path amplitudes'),
            step_reply('Bridge text.', [{'title': 'Adding amplitudes'}, {'title': 'Probability'}]),
        ]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        prompt = self.runner.prompts[0]
        self.assertIn('step 1', prompt)
        self.assertIn('"Amplitudes"', prompt, 'the initial plan comes from the section overview')
        self.assertIn('<lesson-step>', prompt)
        self.assertIn('## Chapter overview', prompt, 'step 1 still opens the chapter')
        lesson = self.lesson()
        self.assertEqual(lesson['id'], 'one')
        self.assertEqual([(s['title'], s['added']) for s in lesson['steps']],
                         [('Path amplitudes', False), ('Complex numbers refresher', True), ('Adding amplitudes', False), ('Probability', False)])
        self.assertEqual(lesson['steps'][0]['turn_id'], 'one')
        self.assertEqual(self.generated(), [], 'grouped practice waits for the last step')

        self.post('/api/lessons/one/steps', {'id': 'two'})
        self.finish('two')
        prompt = self.runner.prompts[1]
        self.assertIn('step 2', prompt)
        self.assertIn('Step one text.', prompt, 'a step sees the steps taught before it')
        self.assertNotIn('Chapter overview', prompt.split('Course route and sources')[0])
        self.assertNotIn('Step one text.\n<lesson-step>', prompt, 'earlier steps reach the prompt without their plan blocks')
        self.assertTrue(self.lesson()['steps'][1]['added'], 'an added step stays marked after a later revision')

        self.runner.replies = [step_reply('Third.'), step_reply('Last.', [])]
        self.post('/api/lessons/one/steps', {'id': 'three'})
        self.finish('three')
        self.assertEqual(self.generated(), [])
        self.post('/api/lessons/one/steps', {'id': 'four'})
        self.finish('four')
        self.assertEqual(len(self.generated()), 1, 'the last step leads to grouped practice')
        self.assertEqual(self.post('/api/lessons/one/steps', {'id': 'five'}, 409)['code'], 'lesson_finished')
        lessons = [t for t in self.state()['turns'] if t['channel'] == 'mainline']
        self.assertEqual([t['id'] for t in lessons], ['one', 'two', 'three', 'four'])

    def test_continue_waits_for_the_current_step_and_retries_are_idempotent(self):
        self.runner.hold.set()
        self.post('/api/lessons', {'id': 'one'})
        self.assertEqual(self.post('/api/lessons/one/steps', {'id': 'two'}, 409)['code'], 'active_turn')
        self.host.pause_turn('one')
        self.host.wait('one', 5)
        self.assertEqual(self.post('/api/lessons/one/steps', {'id': 'two'}, 409)['code'], 'step_unfinished')
        self.runner.hold.clear()
        self.runner.replies = [step_reply('Again.', [{'title': 'Probability'}])]
        self.post('/api/turns/one/resume', {'request_id': 'r1'})
        self.finish('one')
        turn = self.host.operation({'op': 'stream.read', 'id': 'one'})['turn']
        self.assertEqual(turn['attempt'], 2, 'a step regenerates as a new attempt of the same turn')
        self.assertEqual([s['title'] for s in self.lesson()['steps']], ['Amplitudes', 'Probability'])
        self.post('/api/lessons/one/steps', {'id': 'two'})
        self.assertFalse(self.post('/api/lessons/one/steps', {'id': 'two'})['created'])
        self.finish('two')
        self.assertEqual(len(self.lesson()['steps']), 2)

    def test_an_invalid_plan_keeps_the_current_one(self):
        execute(self.root, {'op': 'stream.start', 'id': 'd', 'concept_id': 'state', 'prompt': 'Teach', 'channel': 'mainline'})
        execute(self.root, {'op': 'lesson.begin', 'id': 'l', 'concept_id': 'state', 'steps': ['a', 'b']})
        execute(self.root, {'op': 'lesson.step', 'id': 'l', 'turn_id': 'd'})
        with self.assertRaises(ValueError):
            execute(self.root, {'op': 'lesson.reply', 'id': 'l', 'turn_id': 'd', 'remaining': []})  # not complete yet
        execute(self.root, {'op': 'stream.event', 'id': 'd', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': 'x'})
        execute(self.root, {'op': 'stream.event', 'id': 'd', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
        for remaining in ('not a list', [{'title': ''}], [{'title': 'x'}] * 2, [{'title': f's{i}'} for i in range(8)], [{'title': 'x', 'added': 'yes'}]):
            with self.subTest(remaining=remaining), self.assertRaises(ValueError) as caught:
                execute(self.root, {'op': 'lesson.reply', 'id': 'l', 'turn_id': 'd', 'remaining': remaining})
            self.assertEqual(caught.exception.code, 'invalid_plan')
        with self.assertRaises(ValueError):
            execute(self.root, {'op': 'lesson.begin', 'id': 'l', 'concept_id': 'wave', 'steps': ['a']})
        self.assertEqual([s['title'] for s in execute(self.root, {'op': 'lesson.read', 'id': 'l'})['lesson']['steps']], ['a', 'b'])
        self.runner.replies = [step_reply('Text.', 'not a list'), 'No block at all.']
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        lesson = self.lesson()
        self.assertEqual([s['title'] for s in lesson['steps']], OVERVIEW['steps'])
        self.assertTrue(lesson['steps'][0]['replied'])
        self.post('/api/lessons/one/steps', {'id': 'two'})
        self.finish('two')
        self.assertEqual(len(self.lesson()['steps']), 3, 'a reply without a block keeps the plan')

    def test_old_single_reply_lessons_still_load_and_later_requests_stay_single(self):
        execute(self.root, {'op': 'mainline.enter', 'concept_id': 'wave', 'goal': 'g', 'next_step': 'n', 'request_id': 'p'})
        execute(self.root, {'op': 'stream.start', 'id': 'old', 'concept_id': 'wave', 'prompt': 'Teach', 'channel': 'mainline'})
        execute(self.root, {'op': 'stream.event', 'id': 'old', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': 'A long single reply.'})
        execute(self.root, {'op': 'stream.event', 'id': 'old', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
        state = self.state()
        self.assertEqual(state['lessons'], [])
        self.assertEqual(next(t for t in state['turns'] if t['id'] == 'old')['text'], 'A long single reply.')
        self.post('/api/lessons', {'id': 'again', 'prompt': 'Go deeper'})
        self.finish('again')
        self.assertEqual(self.state()['lessons'], [], 'another pass over a taught section is one reply')
        self.assertIn('already has a lesson', self.runner.prompts[0])
        self.assertEqual(len(self.generated()), 1)
        self.assertEqual(self.post('/api/lessons/old/steps', {'id': 'x'}, 404)['code'], 'unknown_lesson')

    def test_a_step_completed_just_before_a_crash_gets_its_plan_on_reopen(self):
        execute(self.root, {'op': 'lesson.begin', 'id': 'l', 'concept_id': 'state', 'steps': ['a', 'b']})
        execute(self.root, {'op': 'lesson.step', 'id': 'l', 'turn_id': 'd'})
        execute(self.root, {'op': 'stream.start', 'id': 'd', 'concept_id': 'state', 'prompt': 'Teach', 'channel': 'mainline'})
        execute(self.root, {'op': 'stream.event', 'id': 'd', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': step_reply('x', [{'title': 'c'}])})
        execute(self.root, {'op': 'stream.event', 'id': 'd', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
        self.host.navigation.recover()
        self.assertEqual([s['title'] for s in self.lesson('l')['steps']], ['a', 'c'])

    def test_continue_belongs_to_the_current_section(self):
        self.runner.replies = [step_reply('One.', [{'title': 'Two'}])]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        self.host.practice.next_section('wave', 'next')
        self.assertEqual(self.post('/api/lessons/one/steps', {'id': 'two'}, 409)['code'], 'stale_position')


class CheckQuestions(SteppedLessons):
    """Check questions end each lesson step (ADR 0009): answered without a model turn, never evidence."""
    def step_with_check(self, check=CHECK):
        self.runner.replies = [step_reply('One.', [{'title': 'Two'}, {'title': 'Three'}], check=check)]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        return self.lesson()['steps'][0]

    def option(self, check, text):
        return next(i for i, o in enumerate(check['options']) if o['text'] == text)

    def test_a_step_records_a_validated_check_with_explanations_and_the_prompt_asks_for_it(self):
        check = self.step_with_check()['check']
        self.assertIn('"check"', self.runner.prompts[0])
        self.assertIn("I'm not sure", self.runner.prompts[0])
        self.assertEqual(check['question'], CHECK['question'])
        self.assertEqual(check['idea'], CHECK['idea'])
        self.assertEqual(sorted(o['text'] for o in check['options']), sorted(o['text'] for o in CHECK['options']))
        self.assertEqual(check['options'][check['correct']]['text'], 'P = 1', 'the correct option follows any reordering')
        self.assertTrue(all(o['explanation'] for o in check['options']))

    def test_an_invalid_check_is_dropped_and_the_plan_kept(self):
        bad = [{**CHECK, 'correct': 3}, {**CHECK, 'options': CHECK['options'][:1], 'correct': 0}, {**CHECK, 'question': ''},
               {**CHECK, 'options': [{'text': 'x'}, {'text': 'y', 'explanation': 'e'}]}, {**CHECK, 'correct': True}, 'text']
        execute(self.root, {'op': 'lesson.begin', 'id': 'l', 'concept_id': 'state', 'steps': ['a', 'b']})
        execute(self.root, {'op': 'lesson.step', 'id': 'l', 'turn_id': 'd'})
        execute(self.root, {'op': 'stream.start', 'id': 'd', 'concept_id': 'state', 'prompt': 'Teach', 'channel': 'mainline'})
        execute(self.root, {'op': 'stream.event', 'id': 'd', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': 'x'})
        execute(self.root, {'op': 'stream.event', 'id': 'd', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
        for check in bad:
            with self.subTest(check=check), self.assertRaises(ValueError) as caught:
                execute(self.root, {'op': 'lesson.reply', 'id': 'l', 'turn_id': 'd', 'check': check})
            self.assertEqual(caught.exception.code, 'invalid_check')
        self.runner.replies = [step_reply('One.', [{'title': 'Only next'}], check={**CHECK, 'correct': 7})]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        steps = self.lesson()['steps']
        self.assertNotIn('check', steps[0])
        self.assertEqual([s['title'] for s in steps], ['Amplitudes', 'Only next'], 'the valid plan still applies')

    def test_a_wrong_choice_shows_feedback_without_a_model_turn_and_the_next_step_opens_with_a_repair(self):
        check = self.step_with_check()['check']
        turns = len(self.state()['turns'])
        wrong = self.option(check, 'P = 1/2')
        for body in ({'choice': 9}, {'choice': 'maybe'}, {'choice': True}, {}):
            with self.subTest(body=body):
                self.assertEqual(self.post('/api/lessons/one/steps/one/check', body, 409)['code'], 'invalid_choice')
        answered = self.post('/api/lessons/one/steps/one/check', {'choice': wrong})
        self.assertEqual(answered['answer']['choice'], wrong)
        self.assertFalse(answered['answer']['correct'])
        self.assertEqual(len(self.runner.prompts), 1, 'feedback needs no model turn')
        self.assertEqual(len(self.state()['turns']), turns)
        self.assertEqual(self.lesson()['steps'][0]['answer']['choice'], wrong)
        self.assertFalse(self.post('/api/lessons/one/steps/one/check', {'choice': wrong})['changed'], 'a retry is idempotent')
        self.assertEqual(self.post('/api/lessons/one/steps/one/check', {'choice': 0}, 409)['code'], 'already_answered')
        # Recorded as an interaction, never as evidence; it neither makes the section reviewable nor counts as a review.
        interaction = execute(self.root, {'op': 'session.resume', 'recent_limit': 20})['recent_interactions'][-1]
        self.assertEqual(interaction['id'], 'check-answer:one')
        self.assertIn('P = 1/2', interaction['text'])
        self.assertEqual(execute(self.root, {'op': 'evidence.view', 'concept_id': 'wave'})['history'], [])
        self.assertEqual(self.state()['review']['sections'], [])

        self.runner.replies = [step_reply('Two.', [{'title': 'Three'}])]
        self.post('/api/lessons/one/steps', {'id': 'two'})
        self.finish('two')
        prompt = self.runner.prompts[1]
        self.assertIn('repair', prompt)
        self.assertIn('This adds the probabilities', prompt)
        self.assertIn('P = 1/2', prompt)
        self.assertIn('"correct_answer": "P = 1"', prompt)

    def test_not_sure_also_leads_to_a_repair_and_a_correct_choice_does_not(self):
        self.step_with_check()
        self.assertTrue(self.post('/api/lessons/one/steps/one/check', {'choice': 'unsure'})['answer']['unsure'])
        self.runner.replies = [step_reply('Two.', [{'title': 'Three'}], check=CHECK)]
        self.post('/api/lessons/one/steps', {'id': 'two'})
        self.finish('two')
        self.assertIn('not sure', self.runner.prompts[1].split('Lesson plan (data)')[1])
        check = self.lesson()['steps'][1]['check']
        self.assertTrue(self.post('/api/lessons/one/steps/two/check', {'choice': check['correct']})['answer']['correct'])
        self.post('/api/lessons/one/steps', {'id': 'three'})
        self.finish('three')
        self.assertNotIn('repair', self.runner.prompts[2])

    def test_continuing_without_answering_records_nothing_and_closes_the_check(self):
        self.step_with_check()
        self.post('/api/lessons/one/steps', {'id': 'two'})
        self.finish('two')
        self.assertNotIn('repair', self.runner.prompts[1])
        self.assertNotIn('answer', self.lesson()['steps'][0])
        recent = execute(self.root, {'op': 'session.resume', 'recent_limit': 20})['recent_interactions']
        self.assertFalse([i for i in recent if i['id'].startswith('check-answer:')])
        self.assertEqual(self.post('/api/lessons/one/steps/one/check', {'choice': 0}, 409)['code'], 'check_closed')
        self.assertEqual(self.post('/api/lessons/one/steps/two/check', {'choice': 0}, 409)['code'], 'no_check')
        self.assertEqual(self.post('/api/lessons/one/steps/nine/check', {'choice': 0}, 404)['code'], 'unknown_step')


if __name__ == '__main__':
    unittest.main()
