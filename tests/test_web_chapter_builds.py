import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from guided_learning.api import execute
from support import host_client


def build_reply(ref, concept_id='measure', prerequisites=('state',)):
    return json.dumps({
        'summary': 'What a measurement can return.',
        'concepts': [{'id': concept_id, 'title': 'Possible outcomes', 'core_question': 'What can a measurement return?',
                      'objective': 'List the possible outcomes of a measurement', 'prerequisites': list(prerequisites),
                      'links': [ref('line-3')]}],
        'coverage': [{**ref('line-3'), 'disposition': 'mapped', 'concept_ids': [concept_id], 'verification': 'verified', 'verification_note': 'looked'},
                     {**ref('line-4'), 'disposition': 'deferred', 'reason': 'Belongs to time evolution'}]})


class Runner:
    """Answers build turns from `replies` in order (the last one repeats) and every teaching turn with fixed text."""

    def __init__(self, replies=()):
        self.replies = list(replies)
        self.builds = []
        self.hold = None  # an Event a build waits for, when set

    def run(self, prompt, cwd, emit, cancel):
        if 'You build one chapter' in prompt:
            self.builds.append(prompt)
            if self.hold:
                while not self.hold.wait(.01):
                    if cancel.is_set():
                        return
            text = self.replies[min(len(self.builds), len(self.replies)) - 1]
        else:
            text = '{"questions": []}' if 'Practice only' in prompt else 'Lesson text'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


class ChapterBuilds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        execute(self.root, {'op': 'course.init', 'title': 'Quantum'})
        notes = self.root / 'notes.md'
        notes.write_text('A state assigns amplitudes\nAmplitudes add\nOutcomes are eigenvalues\nStates evolve unitarily', encoding='utf-8')
        source = execute(self.root, {'op': 'source.register', 'path': str(notes)})['source']
        self.ref = lambda unit: {'source_id': source['id'], 'revision': source['revision'], 'unit_id': unit}
        execute(self.root, {'op': 'curriculum.outline', 'chapters': [{'id': 'one', 'title': 'States'}, {'id': 'two', 'title': 'Measurement', 'summary': 'Outcomes'},
                                                                     {'id': 'three', 'title': 'Dynamics'}]})
        execute(self.root, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [
            {'id': 'state', 'title': 'What a state represents', 'links': [self.ref('line-1'), self.ref('line-2')]}],
            'coverage': [{**self.ref('line-1'), 'disposition': 'mapped', 'concept_ids': ['state']},
                         {**self.ref('line-2'), 'disposition': 'mapped', 'concept_ids': ['state']}]})
        self.client = None

    def tearDown(self):
        self.close()
        self.tmp.cleanup()

    def open(self, runner):
        self.runner = runner
        self.client, self.host = host_client(self.root, runner=runner)
        self.client.__enter__()

    def close(self):
        if self.client:
            self.client.__exit__(None, None, None)
            self.client = None

    def post(self, path, status=200):
        response = self.client.post(path, json={})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def build(self, chapter_id, until=('done', 'failed'), timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            build = next((b for b in self.client.get('/api/state').json()['builds'] if b['chapter_id'] == chapter_id), None)
            if build and build['status'] in until:
                return build
            time.sleep(.05)
        self.fail(f'build of {chapter_id} did not reach {until}: {build}')

    def chapter(self, chapter_id):
        return execute(self.root, {'op': 'curriculum.chapter.view', 'chapter_id': chapter_id})

    def test_a_build_saves_the_chapter_and_its_coverage(self):
        self.open(Runner([build_reply(self.ref)]))
        self.assertEqual(self.post('/api/chapters/two/build')['build']['status'], 'queued')
        build = self.build('two')
        self.assertEqual(build['status'], 'done')
        self.assertFalse(build.get('discarded'))
        view = self.chapter('two')
        self.assertEqual([c['id'] for c in view['concepts']], ['measure'])
        self.assertEqual(view['chapter']['summary'], 'What a measurement can return.')
        coverage = {e['unit_id']: e for e in execute(self.root, {'op': 'curriculum.view'})['coverage']}
        self.assertEqual(coverage['line-3']['disposition'], 'mapped')
        self.assertEqual(coverage['line-3']['verification'], 'pending', 'the app never marks a location as checked')
        self.assertEqual(coverage['line-4']['disposition'], 'deferred')
        prompt, = self.runner.builds
        self.assertIn('"Measurement" (id two)', prompt)
        self.assertIn('Outcomes are eigenvalues', prompt)
        self.assertNotIn('Amplitudes add', prompt, 'mapped units are not sent again')
        self.assertIn('What a state represents', prompt)
        self.assertIn('English', prompt)
        state = self.client.get('/api/state').json()
        self.assertFalse(any('Possible outcomes' in i.get('text', '') for i in state['session']['recent_interactions']))

    def test_a_rejected_reply_is_retried_once_with_the_error(self):
        self.open(Runner(['not json at all', build_reply(self.ref)]))
        self.post('/api/chapters/two/build')
        self.assertEqual(self.build('two')['status'], 'done')
        first, second = self.runner.builds
        self.assertNotIn('could not be saved', first)
        self.assertIn('could not be saved', second)
        self.assertIn('not valid JSON', second)
        self.assertIn('not json at all', second)

    def test_two_rejected_replies_record_the_failure(self):
        bad = build_reply(self.ref, prerequisites=['nowhere'])
        self.open(Runner([bad]))
        self.post('/api/chapters/two/build')
        build = self.build('two')
        self.assertEqual(build['status'], 'failed')
        self.assertIn('Unknown prerequisite', build['error'])
        self.assertEqual(len(self.runner.builds), 2)
        self.assertIn('Unknown prerequisite', self.runner.builds[1])
        self.assertEqual(self.chapter('two')['concepts'], [])
        time.sleep(.3)
        self.assertEqual(len(self.runner.builds), 2, 'no further attempts')
        # The learner can try again.
        self.assertEqual(self.post('/api/chapters/two/build')['build']['status'], 'queued')

    def test_reusing_an_existing_concept_id_is_rejected(self):
        self.open(Runner([build_reply(self.ref, concept_id='state', prerequisites=[])]))
        self.post('/api/chapters/two/build')
        build = self.build('two')
        self.assertEqual(build['status'], 'failed')
        self.assertIn('already exists', build['error'])
        self.assertEqual([c['id'] for c in self.chapter('one')['concepts']], ['state'])

    def test_a_chapter_built_elsewhere_meanwhile_keeps_that_build(self):
        runner = Runner([build_reply(self.ref)])
        runner.hold = threading.Event()
        self.open(runner)
        self.post('/api/chapters/two/build')
        self.build('two', until=('building',))
        deadline = time.monotonic() + 5
        while not runner.builds and time.monotonic() < deadline:
            time.sleep(.02)
        execute(self.root, {'op': 'curriculum.chapter.save', 'chapter_id': 'two', 'concepts': [{'id': 'codex-made', 'title': 'Built in Codex', 'prerequisites': ['state']}]})
        runner.hold.set()
        build = self.build('two')
        self.assertEqual(build['status'], 'done')
        self.assertTrue(build['discarded'])
        self.assertEqual([c['id'] for c in self.chapter('two')['concepts']], ['codex-made'])

    def test_an_exercise_placed_before_what_it_needs_is_rejected_and_retried(self):
        reply = json.loads(build_reply(self.ref))
        reply['concepts'][0]['exercises'] = [{'question': '3(b)', **self.ref('line-3'), 'required_concepts': ['measure', 'evolution']}]
        self.open(Runner([json.dumps(reply), build_reply(self.ref)]))
        self.post('/api/chapters/two/build')
        self.assertEqual(self.build('two')['status'], 'done')
        first, second = self.runner.builds
        self.assertIn('required_concepts', first)
        self.assertIn('could not be saved', second)
        self.assertIn('Exercise "3(b)"', second)
        self.assertIn('"evolution"', second)

    def test_a_course_with_misplaced_exercises_still_opens_teaches_and_builds(self):
        from guided_learning.store import Store
        store = Store(self.root)
        with store.db:
            model = store.get('curriculum', 'model')
            model['concepts'][0]['exercises'] = [{'question': '1', **self.ref('line-1'), 'required_concepts': ['eigenvalues']}]
            store.put('curriculum', 'model', model)
        store.db.close()
        self.assertEqual(len(execute(self.root, {'op': 'curriculum.check'})['violations']), 1)
        self.open(Runner([build_reply(self.ref)]))
        self.assertEqual(self.client.get('/api/state').status_code, 200)
        turn = self.post('/api/lessons')['turn']
        self.assertEqual(self.host.wait(turn['id'], 5)['status'], 'completed')
        self.assertEqual(self.client.get('/api/state').json()['curriculum']['concepts'][0]['exercises'][0]['question'], '1')
        # The app's build of the next chapter saves despite the violation it does not touch.
        self.assertEqual(self.build('two')['status'], 'done')
        self.assertEqual(len(execute(self.root, {'op': 'curriculum.check'})['violations']), 1)

    def test_homework_parts_left_for_later_chapters_reach_their_builds(self):
        execute(self.root, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [
            {'id': 'state', 'title': 'What a state represents', 'links': [self.ref('line-1'), self.ref('line-2')],
             'exercises': [{'question': '1(a)', **self.ref('line-2'), 'required_concepts': ['state'], 'part_of': '1',
                            'other_parts': [{'question': '1(b)'}]}]}]})
        self.open(Runner([build_reply(self.ref)]))
        self.post('/api/chapters/two/build')
        self.assertEqual(self.build('two')['status'], 'done')
        data = lambda prompt: json.loads(next(line for line in prompt.split('\n') if line.startswith('{"course"')))
        waiting = data(self.runner.builds[0])['waiting_parts']
        self.assertEqual(waiting, [{'question': '1(b)', 'part_of': '1', **self.ref('line-2'), 'text': 'Amplitudes add',
                                    'mapped_part': {'question': '1(a)', 'concept_id': 'state'}}])
        execute(self.root, {'op': 'curriculum.chapter.save', 'chapter_id': 'two', 'concepts': [
            {'id': 'measure', 'title': 'Possible outcomes', 'prerequisites': ['state'], 'links': [self.ref('line-3')],
             'exercises': [{'question': '1(b)', **self.ref('line-2'), 'required_concepts': ['measure'], 'part_of': '1',
                            'other_parts': [{'question': '1(a)', 'concept_id': 'state'}]}]}]})
        self.post('/api/chapters/three/build')
        self.build('three')
        self.assertNotIn('waiting_parts', data(self.runner.builds[-1]))

    def test_studying_the_last_built_chapter_builds_the_next(self):
        self.open(Runner([build_reply(self.ref)]))
        turn = self.post('/api/lessons')['turn']
        self.host.wait(turn['id'], 5)
        build = self.build('two')
        self.assertEqual((build['status'], build['trigger']), ('done', 'auto'))
        self.assertEqual([c['id'] for c in self.chapter('two')['concepts']], ['measure'])
        # Chapter two is now the last built one, but the learner is still in chapter one.
        time.sleep(.3)
        self.assertFalse(any(b['chapter_id'] == 'three' for b in self.client.get('/api/state').json()['builds']))

    def test_a_build_stopped_by_a_restart_is_shown_interrupted_and_can_be_retried(self):
        runner = Runner([build_reply(self.ref)])
        runner.hold = threading.Event()
        self.open(runner)
        self.post('/api/chapters/two/build')
        self.build('two', until=('building',))
        self.close()
        self.open(Runner([build_reply(self.ref)]))
        build = self.build('two', until=('interrupted',))
        self.assertIn('stopped', build['error'])
        self.post('/api/chapters/two/build')
        self.assertEqual(self.build('two')['status'], 'done')

    def test_only_outlined_unbuilt_chapters_build_one_at_a_time(self):
        runner = Runner([build_reply(self.ref)])
        runner.hold = threading.Event()
        self.open(runner)
        self.assertEqual(self.post('/api/chapters/one/build', 409)['code'], 'not_buildable')
        self.assertEqual(self.post('/api/chapters/nowhere/build', 409)['code'], 'not_buildable')
        self.post('/api/chapters/two/build')
        self.assertEqual(self.post('/api/chapters/two/build')['build']['chapter_id'], 'two', 'asking again is harmless')
        self.assertEqual(self.post('/api/chapters/three/build', 409)['code'], 'build_busy')
        runner.hold.set()
        self.build('two')


if __name__ == '__main__':
    unittest.main()
