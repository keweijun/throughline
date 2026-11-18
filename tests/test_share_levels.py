"""Share levels below Everything (ADR 0020): a recipient starts fresh with the route, and with the lessons and
exercises the sender's teacher wrote, revealed as they study, without the sender's answers, memory or prompts."""
import json
import sqlite3
import tempfile
from pathlib import Path

from guided_learning import packages
from guided_learning.api import execute
from guided_learning.streaming import PREPARED_STEP
from support import host_client
from test_web_lessons import CHECK, LessonHost, Runner, step_reply


MINE, ON_STEP = '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002'


def records(course):
    db = sqlite3.connect(Path(course) / 'course.sqlite3')
    try:
        return {(n, k): json.loads(v) for n, k, v in db.execute('SELECT namespace, key, value FROM documents')}
    finally:
        db.close()


class SharedLessons(LessonHost):
    def setUp(self):
        super().setUp()
        execute(self.root, {'op': 'course.profile.save', 'profile': {'goal': 'Pass the exam in a week', 'depth': 'standard', 'focus': 'Problem sets',
                                                                       'prerequisites': [{'topic': 'Calculus', 'level': 'some'}], 'notes': 'Hates long derivations'}})
        execute(self.root, {'op': 'memory.save', 'id': 'pref', 'kind': 'preference', 'text': 'Prefers worked examples', 'concept_id': 'wave'})
        # The sender studies two of three steps, misses the check, and attempts the exercise.
        self.runner.replies = [step_reply('Step one text.', [{'title': 'Adding amplitudes'}, {'title': 'Probability'}], title='Amplitudes', check=CHECK),
                               step_reply('Step two text.')]
        self.post('/api/lessons', {'id': 'one'})
        self.finish('one')
        self.post('/api/lessons/one/steps/one/check', {'choice': 1})
        self.proceed('two')
        self.finish('two')
        self.client.__exit__(None, None, None)
        db = sqlite3.connect(self.root / 'course.sqlite3')
        task = {'id': 'task-1', 'concept_id': 'wave', 'question': 'Find P.', 'origin': 'self_created', 'source_refs': [], 'status': 'attempted',
                'history': [{'action': 'assess', 'answer': 'P = 1/2', 'feedback': 'Add amplitudes first.', 'outcome': 'needs_work'}], 'created_at': 1}
        quiz = {**task, 'id': 'quiz-1', 'origin': 'chapter_quiz', 'chapter_id': 'c1', 'history': []}
        for item in (task, quiz):
            db.execute('INSERT INTO documents VALUES (?, ?, ?)', ('practice_tasks', item['id'], json.dumps(item)))
        db.commit()
        db.close()
        self.client, self.host = host_client(self.root, runner=self.runner, port=8768)
        self.client.__enter__()  # tearDown closes it
        self.library = Path(self.tmp.name) / 'library'
        self.library.mkdir()

    def share(self, level, **options):
        package = Path(self.tmp.name) / f'{level}.throughline'
        packages.export(self.root, package, level)
        return Path(packages.import_package(package, self.library, **options)['path'])

    def test_route_and_lessons_carries_what_the_teacher_wrote_and_none_of_the_sender(self):
        course = self.share('lessons')
        kept = records(course)
        namespaces = {n for n, _ in kept}
        self.assertEqual(namespaces & {'interactions', 'evidence', 'memory', 'memory_notes', 'stream_snapshots', 'web_branches', 'annotations',
                                       'preparation_jobs', 'preparation_payloads', 'practice_jobs', 'checkpoint_receipts'}, set())
        self.assertNotIn(('course', 'position'), kept)
        self.assertNotIn(('course', 'profile'), kept)
        self.assertEqual(kept[('course', 'built_for')], {'goal': 'Pass the exam in a week', 'depth': 'standard', 'focus': 'Problem sets'})
        self.assertEqual(kept[('course', 'imported')]['level'], 'lessons')
        lesson = kept[('lessons', 'one')]
        self.assertEqual([(s['title'], s.get('written'), 'turn_id' in s, 'answer' in s) for s in lesson['steps']],
                         [('Amplitudes', self.turn_id('one'), False, False), ('Adding amplitudes', self.turn_id('two'), False, False),
                          ('Probability', None, False, False)])
        self.assertEqual(lesson['steps'][0]['check']['question'], CHECK['question'])
        self.assertNotIn('prepared', lesson)
        turns = {k: v for (n, k), v in kept.items() if n == 'streams'}
        self.assertEqual(set(turns), {self.turn_id('one'), self.turn_id('two')}, 'only written lesson steps travel')
        self.assertTrue(all(t['channel'] == PREPARED_STEP and 'prompt_snapshot' not in t for t in turns.values()))
        self.assertEqual({k: (v['status'], v['history']) for (n, k), v in kept.items() if n == 'practice_tasks'}, {'task-1': ('pending', [])},
                         'exercises keep no attempts, and chapter quizzes stay behind')
        everything = json.dumps(list(kept.values()), ensure_ascii=False)
        for private in ('Hates long derivations', 'Prefers worked examples', 'Calculus', 'Add amplitudes first.'):
            self.assertNotIn(private, everything, 'nothing of the sender beyond the built-for note travels')

    def test_the_recipient_reveals_written_steps_without_a_teacher_turn_and_starts_unstudied(self):
        course = self.share('lessons')
        runner = Runner()
        runner.replies = [step_reply('Step three, by the recipient\'s teacher.', [])]
        self.client.__exit__(None, None, None)
        self.client, self.host = host_client(course, runner=runner, port=8766)
        self.client.__enter__()
        state = self.state()
        self.assertEqual([t for t in state['turns'] if t['channel'] == 'mainline'], [], 'every section starts unstudied')
        shown = self.post('/api/lessons', {'id': 'r1'})
        self.assertEqual((shown['turn']['id'], shown['turn']['final_text'].split('\n')[0]), (self.turn_id('one'), 'Step one text.'))
        self.assertEqual(runner.prompts, [], 'a written step needs no teacher turn')
        lesson = self.lesson()
        self.assertNotIn('answer', lesson['steps'][0], "the sender's check answer stays behind")
        self.assertFalse(self.post(f"/api/lessons/one/steps/{self.turn_id('one')}/check", {'choice': CHECK['correct']})['answer']['unsure'])
        second = self.post('/api/lessons/one/steps', {'id': 'r2'})
        self.assertEqual(second['turn']['id'], self.turn_id('two'))
        self.finish(self.turn_id('two'))
        third = self.post('/api/lessons/one/steps', {'id': 'r3'})
        self.finish(third['turn']['id'])
        steps = self.lesson()['steps']
        self.assertTrue(all(s.get('turn_id') and 'written' not in s for s in steps))
        mainline = [t['id'] for t in self.state()['turns'] if t['channel'] == 'mainline']
        self.assertEqual(mainline[:2], [self.turn_id('one'), self.turn_id('two')])
        self.assertEqual(len(mainline), 3, "the plan's last step is written by the recipient's teacher")
        self.assertTrue(any('step 3' in p for p in runner.prompts))

    def test_route_carries_no_lessons_or_exercises(self):
        kept = records(self.share('route'))
        self.assertEqual({n for n, _ in kept} & {'lessons', 'streams', 'practice_tasks'}, set())
        self.assertIn('curriculum', {n for n, _ in kept})
        self.assertIn(('course', 'built_for'), kept)

    def test_an_everything_package_can_be_started_fresh(self):
        package = Path(self.tmp.name) / 'all.throughline'
        packages.export(self.root, package)
        self.assertEqual(packages.inspect(package)['modes'], ['continue', 'fresh', 'fresh-with-notes'])
        fresh = records(Path(packages.import_package(package, self.library, mode='fresh')['path']))
        self.assertEqual({n for n, _ in fresh} & {'interactions', 'evidence', 'memory'}, set())
        self.assertIn(('lessons', 'one'), fresh)
        lessons = Path(tempfile.mkdtemp(dir=self.tmp.name)) / 'lessons.throughline'
        packages.export(self.root, lessons, 'lessons')
        self.assertEqual(packages.inspect(lessons)['modes'], ['fresh'])
        with self.assertRaises(packages.OperationError) as refused:
            packages.import_package(lessons, self.library, mode='continue')
        self.assertEqual(refused.exception.code, 'invalid_request')

    def test_starting_fresh_can_keep_the_senders_notes_and_questions_to_read(self):
        self.post('/api/questions', {'id': 'q', 'question': 'Why add amplitudes first?', 'main_turn_id': self.turn_id('two')})
        self.assertEqual(self.host.wait('branch:q', 5)['status'], 'completed')
        self.post('/api/annotations', {'id': MINE, 'kind': 'note', 'concept_id': 'wave', 'note': 'Amplitudes, then squares'})
        self.post('/api/annotations', {'id': ON_STEP, 'kind': 'highlight', 'turn_id': self.turn_id('one'), 'passage': 'Step one text.'})
        package = Path(self.tmp.name) / 'all.throughline'
        packages.export(self.root, package)
        self.client.__exit__(None, None, None)
        course = Path(packages.import_package(package, self.library, mode='fresh-with-notes')['path'])
        kept = records(course)
        self.assertEqual({n for n, _ in kept} & {'interactions', 'evidence', 'memory', 'stream_snapshots'}, set())
        self.assertEqual(kept[('course', 'imported')]['notes'], True)
        branch = kept[('web_branches', 'q')]
        self.assertEqual((branch['from_sender'], branch['status']), (True, 'answered'))
        self.assertEqual(kept[('streams', 'branch:q')]['channel'], 'sidequestion')
        self.assertEqual({k for (n, k) in kept if n == 'annotations'}, {MINE, ON_STEP})
        self.assertTrue(all(v['from_sender'] for (n, _), v in kept.items() if n == 'annotations'))

        runner = Runner()
        self.client, self.host = host_client(course, runner=runner, port=8767)
        self.client.__enter__()
        self.assertEqual(self.client.put('/api/annotations/' + MINE, json={'note': 'Changed'}).json()['code'], 'read_only')
        self.assertEqual(self.client.delete('/api/annotations/' + MINE).status_code, 200, "the recipient may delete the sender's note")
        refused = self.client.post('/api/questions/q/replies', json={'id': 'follow', 'question': 'And phases?'})
        self.assertEqual(refused.json()['code'], 'read_only')
        self.assertEqual(execute(course, {'op': 'session.resume'})['app_questions'], [])
        self.post('/api/lessons', {'id': 'r1'})
        self.post('/api/lessons/one/steps', {'id': 'r2'})
        self.post('/api/lessons/one/steps', {'id': 'r3'})
        self.finish(self.lesson()['steps'][2]['turn_id'])
        self.assertTrue(runner.prompts)
        self.assertFalse(any('Why add amplitudes first?' in p for p in runner.prompts), "the sender's questions never reach the teacher")
