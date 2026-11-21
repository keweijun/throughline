"""Key points (ADR 0024): the lesson's last step writes a section's points, another pass may rewrite them, an
idle job writes them for sections studied before, and Codex changes them when the learner asks."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from guided_learning import packages
from guided_learning.api import execute
from guided_learning.store import OperationError
from support import host_client, settle
from test_web_lessons import LessonHost, Runner, step_reply

POINT = {'statement': 'Amplitudes add before squaring: $P = |a_1 + a_2|^2$.', 'holds_when': 'The paths are indistinguishable.',
         'common_mistake': 'Adding the probabilities instead.'}


def last_step(text, points):
    return text + '\n<lesson-step>' + json.dumps({'remaining': [], 'key_points': points}) + '</lesson-step>'


class Points(unittest.TestCase):
    """The operations, on a course with one studied section."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        notes = self.root / 'notes.md'
        notes.write_text('# Waves\nAmplitudes add.\n', encoding='utf-8')
        execute(self.root, {'op': 'course.init', 'title': 'Quantum'})
        source = execute(self.root, {'op': 'source.register', 'path': str(notes)})['source']
        unit = execute(self.root, {'op': 'source.read', 'source_id': source['id']})['units'][0]
        self.ref = {'source_id': source['id'], 'revision': source['revision'], 'unit_id': unit['id']}
        execute(self.root, {'op': 'curriculum.save', 'route': ['wave', 'state'], 'coverage': [],
                            'chapters': [{'id': 'c1', 'title': 'Basics', 'concept_ids': ['wave', 'state']}],
                            'concepts': [{'id': 'wave', 'title': 'Wave', 'links': [self.ref]}, {'id': 'state', 'title': 'State'}]})

    def tearDown(self):
        self.tmp.cleanup()

    def op(self, **request):
        return execute(self.root, request)

    def study(self, cid, identifier):
        self.op(op='stream.start', id=identifier, concept_id=cid, prompt='Teach', record_user=False)
        self.op(op='stream.event', id=identifier, attempt=1, sequence=1, kind='final', text='Taught.')
        self.op(op='stream.event', id=identifier, attempt=1, sequence=2, kind='complete')

    def test_points_belong_to_a_studied_section_and_link_only_to_its_lessons_and_pages(self):
        with self.assertRaises(OperationError) as refused:
            self.op(op='key_points.save', concept_id='wave', turn_id='t1', origin='lesson', points=[POINT])
        self.assertEqual(refused.exception.code, 'not_studied')
        self.study('wave', 't1')
        saved = self.op(op='key_points.save', concept_id='wave', turn_id='t1', origin='lesson',
                        points=[{**POINT, 'turn_id': 't1', 'source_refs': [self.ref]}, {'statement': 'Phases matter.', 'common_mistake': ''}])
        self.assertEqual(saved['key_points']['points'][0]['source_refs'], [self.ref])
        self.assertEqual(saved['key_points']['points'][1], {'statement': 'Phases matter.', 'source_refs': []}, 'an empty field is left out')
        for bad in ([{**POINT, 'turn_id': 'elsewhere'}], [{**POINT, 'source_refs': [{**self.ref, 'unit_id': 'other'}]}],
                    [POINT, POINT], [], [{'holds_when': 'always'}], [POINT] * 13):
            with self.assertRaises(OperationError) as invalid:
                self.op(op='key_points.save', concept_id='wave', turn_id='t2', origin='lesson', points=bad)
            self.assertEqual(invalid.exception.code, 'invalid_key_points')
        self.assertFalse(self.op(op='key_points.save', concept_id='wave', turn_id='t1', origin='lesson', points=[POINT])['changed'],
                         'a turn writes its points once')

    def test_codex_revises_points_and_the_change_asked_for_outlasts_a_rewrite(self):
        self.study('wave', 't1')
        self.op(op='key_points.save', concept_id='wave', turn_id='t1', origin='lesson', points=[POINT])
        revised = self.op(op='key_points.revise', concept_id='wave', points=[{**POINT, 'statement': 'Add amplitudes, then square.'}],
                          request='Say it in plain words')['key_points']
        self.assertEqual((revised['origin'], [r['text'] for r in revised['requests']]), ('codex', ['Say it in plain words']))
        with self.assertRaises(OperationError) as missing:
            self.op(op='key_points.revise', concept_id='wave', points=[POINT])
        self.assertEqual(missing.exception.code, 'invalid_key_points', 'a revision says what the learner asked for')
        with self.assertRaises(OperationError) as unstudied:
            self.op(op='key_points.revise', concept_id='state', points=[POINT], request='Add one')
        self.assertEqual(unstudied.exception.code, 'not_studied')
        self.study('wave', 't2')
        rewritten = self.op(op='key_points.save', concept_id='wave', turn_id='t2', origin='lesson', points=[POINT])['key_points']
        self.assertEqual([r['text'] for r in rewritten['requests']], ['Say it in plain words'])

    def test_pending_lists_sections_without_points_and_chapters_whose_paragraph_is_missing_or_stale(self):
        self.study('wave', 't1')
        self.study('state', 't2')
        self.assertEqual(self.op(op='key_points.pending')['sections'], ['wave', 'state'])
        self.assertEqual(self.op(op='key_points.pending', exclude=['state'])['sections'], ['wave'])
        self.op(op='key_points.save', concept_id='wave', turn_id='t1', origin='lesson', points=[POINT])
        self.assertEqual(self.op(op='key_points.pending')['chapters'], [], 'one section with points has nothing to connect')
        self.op(op='key_points.save', concept_id='state', turn_id='t2', origin='backfill', points=[{'statement': 'A state is a ray.'}])
        chapter = self.op(op='key_points.pending')['chapters'][0]
        self.op(op='key_points.save_sheet', chapter_id='c1', basis=chapter['basis'], connection='Waves give states.', turn_id='s1')
        self.assertEqual(self.op(op='key_points.pending')['chapters'], [])
        self.assertTrue(self.op(op='key_points.view')['chapter_sheets'][0]['current'])
        self.op(op='key_points.revise', concept_id='state', points=[{'statement': 'A state is a unit ray.'}], request='Be precise')
        self.assertFalse(self.op(op='key_points.view')['chapter_sheets'][0]['current'], 'new points leave the paragraph behind')
        self.assertEqual([c['chapter_id'] for c in self.op(op='key_points.pending')['chapters']], ['c1'])


class LessonPoints(LessonHost):
    """The lesson writes the points as it ends."""

    def points(self, cid='wave'):
        return next((v for v in self.state()['key_points'] if v['concept_id'] == cid), {})

    def test_the_last_step_writes_the_points_linked_to_the_steps_that_taught_them(self):
        self.runner.replies = [step_reply('Step one.', [{'title': 'Probability'}], title='Amplitudes'),
                               last_step('Step two.', [{**POINT, 'step': 1}, {'statement': 'Probabilities follow.', 'step': 2, 'sources': [{'source_id': 'x', 'unit_id': 'y'}]}])]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        self.assertEqual(self.points(), {}, 'a step with steps after it writes no points')
        self.assertIn('"key_points"', self.prompt(1), 'every step is told how to end the lesson')
        self.proceed('two')
        self.finish('two')
        written = self.points()
        self.assertEqual([(p['statement'], p.get('turn_id')) for p in written['points']],
                         [(POINT['statement'], self.turn_id('one')), ('Probabilities follow.', self.turn_id('two'))])
        self.assertEqual(written['points'][1]['source_refs'], [], 'a citation the section does not link to is dropped')
        self.assertEqual(written['origin'], 'lesson')

    def test_a_later_single_reply_lesson_rewrites_the_points_keeping_what_it_keeps_and_what_was_asked(self):
        self.runner.replies = [last_step('The whole lesson.', [{**POINT, 'step': 1}])]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        execute(self.root, {'op': 'key_points.revise', 'concept_id': 'wave', 'request': 'Mention the phase',
                            'points': [{**POINT, 'turn_id': self.turn_id('one')}, {'statement': 'The phase sets the interference.'}]})
        self.runner.replies = ['Taught again.\n<key-points>' + json.dumps({'points': [{'kept': 0}, {'statement': 'Paths can cancel.', 'taught_here': True}]}) + '</key-points>']
        self.post('/api/lessons', {'id': 'again', 'prompt': 'Teach it again from scratch'})
        self.finish('again')
        prompt = self.runner.prompts[-1]
        self.assertIn('Mention the phase', prompt)
        self.assertIn('The phase sets the interference.', prompt)
        written = self.points()
        self.assertEqual([(p['statement'], p.get('turn_id')) for p in written['points']],
                         [(POINT['statement'], self.turn_id('one')), ('Paths can cancel.', 'again')])
        self.assertEqual([r['text'] for r in written['requests']], ['Mention the phase'])
        shown = next(t for t in self.state()['turns'] if t['id'] == 'again')
        self.assertIn('<key-points>', shown['text'], 'the interface hides the block, as it hides memory notes')

    def test_a_new_lesson_rewrites_the_points_from_its_last_step_keeping_what_was_asked(self):
        self.runner.replies = [last_step('The first lesson.', [{**POINT, 'step': 1}])]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        execute(self.root, {'op': 'key_points.revise', 'concept_id': 'wave', 'request': 'Mention the phase',
                            'points': [{**POINT, 'turn_id': self.turn_id('one')}]})
        self.runner.replies = [last_step('Taught anew.', [{'kept': 0}, {'statement': 'The phase sets the interference.', 'step': 1}])]
        self.post('/api/lessons', {'id': 'two', 'kind': 'new'})
        self.finish('two')
        self.assertIn('Mention the phase', self.prompt(1))
        written = self.points()
        self.assertEqual([(p['statement'], p.get('turn_id')) for p in written['points']],
                         [(POINT['statement'], self.turn_id('one')), ('The phase sets the interference.', 'two')])
        self.assertEqual(written['turn_id'], 'two')

    def test_a_single_reply_without_a_block_keeps_the_points(self):
        self.runner.replies = [last_step('The whole lesson.', [POINT]), 'More on the same.']
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        self.post('/api/lessons', {'id': 'more', 'prompt': 'One more example'})
        self.finish('more')
        self.assertEqual([p['statement'] for p in self.points()['points']], [POINT['statement']])


class IdleRunner(Runner):
    def __init__(self):
        super().__init__()
        self.jobs = []
        self.backfill = '<key-points>' + json.dumps({'points': [{**POINT, 'lesson': 1}]}) + '</key-points>'

    def run(self, prompt, cwd, emit, cancel):
        if 'Write the key points of this section from its lessons.' in prompt:
            self.jobs.append(('section', prompt))
            emit({'kind': 'final', 'text': self.backfill})
            emit({'kind': 'complete'})
            return
        if "Write how this chapter's key points connect." in prompt:
            self.jobs.append(('chapter', prompt))
            emit({'kind': 'final', 'text': '<chapter-sheet>{"connection": "Waves lead to states."}</chapter-sheet>'})
            emit({'kind': 'complete'})
            return
        super().run(prompt, cwd, emit, cancel)


class IdlePoints(unittest.TestCase):
    """Sections studied before key points get theirs while the host is idle, and chapters their paragraph."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        execute(self.root, {'op': 'course.init', 'title': 'Quantum'})
        execute(self.root, {'op': 'curriculum.save', 'route': ['wave', 'state', 'spin'], 'coverage': [],
                            'chapters': [{'id': 'c1', 'title': 'Basics', 'concept_ids': ['wave', 'state']}, {'id': 'c2', 'title': 'Spin', 'concept_ids': ['spin']}],
                            'concepts': [{'id': 'wave', 'title': 'Wave'}, {'id': 'state', 'title': 'State'}, {'id': 'spin', 'title': 'Spin'}]})
        for cid in ('wave', 'state'):
            execute(self.root, {'op': 'stream.start', 'id': 'old-' + cid, 'concept_id': cid, 'prompt': 'Teach', 'record_user': False})
            execute(self.root, {'op': 'stream.event', 'id': 'old-' + cid, 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': f'The old {cid} lesson.'})
            execute(self.root, {'op': 'stream.event', 'id': 'old-' + cid, 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
        self.runner = IdleRunner()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def open(self, key_points=True):
        self.client, self.host = host_client(self.root, runner=self.runner, key_points=key_points)
        self.client.__enter__()

    def wait_for(self, check, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            settle(self.host)
            if check():
                return
            self.host.preparation.wake()
            time.sleep(.05)
        self.fail('the idle job did not finish')

    def test_points_for_each_studied_section_then_the_chapter_paragraph_once(self):
        self.open()
        self.wait_for(lambda: self.client.get('/api/state').json()['chapter_sheets'])
        state = self.client.get('/api/state').json()
        self.assertEqual({v['concept_id']: (v['origin'], v['points'][0].get('turn_id')) for v in state['key_points']},
                         {'wave': ('backfill', 'old-wave'), 'state': ('backfill', 'old-state')})
        self.assertEqual([kind for kind, _ in self.runner.jobs], ['section', 'section', 'chapter'])
        self.assertIn('The old wave lesson.', self.runner.jobs[0][1])
        self.assertIn('Amplitudes add before squaring', self.runner.jobs[2][1])
        self.assertEqual(state['chapter_sheets'][0]['connection'], 'Waves lead to states.')
        self.host.preparation.wake()
        time.sleep(.3)
        settle(self.host)
        self.assertEqual(len(self.runner.jobs), 3, 'nothing is written twice')

    def test_a_failed_job_is_not_tried_again_for_the_same_lessons(self):
        self.runner.backfill = 'No block at all.'
        self.open()
        self.wait_for(lambda: len(self.runner.jobs) >= 2)
        time.sleep(.3)
        self.host.preparation.wake()
        settle(self.host)
        self.assertEqual([kind for kind, _ in self.runner.jobs], ['section', 'section'])
        self.assertEqual(self.client.get('/api/state').json()['key_points'], [])

    def test_a_section_taught_anew_is_summed_up_from_its_current_lesson(self):
        execute(self.root, {'op': 'lesson.begin', 'id': 'old', 'concept_id': 'wave', 'steps': ['Wave']})
        execute(self.root, {'op': 'lesson.step', 'id': 'old', 'turn_id': 'old-wave'})
        execute(self.root, {'op': 'stream.start', 'id': 'new-wave', 'concept_id': 'wave', 'prompt': 'Teach', 'record_user': False})
        execute(self.root, {'op': 'lesson.begin', 'id': 'new', 'concept_id': 'wave', 'steps': ['Wave']})
        execute(self.root, {'op': 'lesson.step', 'id': 'new', 'turn_id': 'new-wave'})
        execute(self.root, {'op': 'stream.event', 'id': 'new-wave', 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': 'The new wave lesson.'})
        execute(self.root, {'op': 'stream.event', 'id': 'new-wave', 'attempt': 1, 'sequence': 2, 'kind': 'complete'})
        self.open()
        self.wait_for(lambda: len(self.client.get('/api/state').json()['key_points']) == 2)
        prompt = next(p for kind, p in self.runner.jobs if kind == 'section' and 'section "Wave"' in p)
        taught = prompt.split('Lessons taught (data): ')[1]
        self.assertIn('The new wave lesson.', taught)
        self.assertNotIn('The old wave lesson.', taught, 'the lesson a New lesson replaced is history')
        wave = next(v for v in self.client.get('/api/state').json()['key_points'] if v['concept_id'] == 'wave')
        self.assertEqual(wave['points'][0]['turn_id'], 'new-wave')

    def test_off_in_tests_unless_asked(self):
        self.open(key_points=False)
        time.sleep(.5)
        settle(self.host)
        self.assertEqual(self.runner.jobs, [])


class SharedPoints(LessonHost):
    def test_points_travel_with_the_lessons_but_not_what_the_sender_asked(self):
        self.runner.replies = [last_step('The whole lesson.', [{**POINT, 'step': 1}])]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        execute(self.root, {'op': 'key_points.revise', 'concept_id': 'wave', 'request': 'My private wish',
                            'points': [{**POINT, 'turn_id': self.turn_id('one')}]})
        self.client.__exit__(None, None, None)
        package = Path(self.tmp.name) / 'lessons.throughline'
        packages.export(self.root, package, 'lessons')
        library = Path(self.tmp.name) / 'library'
        library.mkdir()
        course = Path(packages.import_package(package, library)['path'])
        shared = execute(course, {'op': 'key_points.view'})['key_points'][0]
        self.assertEqual((shared['requests'], shared['points'][0]['turn_id']), ([], self.turn_id('one')))
        self.client, self.host = host_client(self.root, runner=self.runner, port=8769)
        self.client.__enter__()


if __name__ == '__main__':
    unittest.main()
