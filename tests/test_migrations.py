import sqlite3
import tempfile
import unittest
from pathlib import Path

from guided_learning import library, migrations
from guided_learning.api import execute
from guided_learning.store import OperationError


class Migrations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / 'course'
        execute(self.workspace, {'op': 'course.init', 'title': 'Quantum'})

    def raw(self, sql, *args):
        """Edit the database the way an older Throughline left it, bypassing operations."""
        db = sqlite3.connect(self.workspace / 'course.sqlite3')
        try:
            rows = db.execute(sql, args).fetchall()
            db.commit()
            return rows
        finally:
            db.close()

    def put(self, namespace, key, value):
        import json
        self.raw('INSERT OR REPLACE INTO documents VALUES (?, ?, ?)', namespace, key, json.dumps(value))

    def stored_version(self):
        import json
        rows = self.raw("SELECT value FROM documents WHERE namespace='course' AND key='schema'")
        return json.loads(rows[0][0])['version'] if rows else None

    def test_a_new_course_starts_at_the_current_version(self):
        self.assertEqual(self.stored_version(), migrations.VERSION)

    def test_an_unversioned_course_is_migrated_on_its_next_operation(self):
        self.raw("DELETE FROM documents WHERE namespace='course' AND key='schema'")
        lesson = {'id': 'a', 'concept_id': 'a', 'status': 'completed', 'final_text': 'Lesson text', 'text': 'Lesson text',
                  'source_refs': [{'source_id': 's', 'revision': 'r', 'unit_id': 'u'}],
                  'prompt_snapshot': {'context': {'concept': {'id': 'a', 'title': 'States'}}, 'route': ['huge']}}
        branch = {'id': 'q', 'turn_id': 'branch:q', 'selected_lecture': lesson, 'replies': []}
        self.put('web_branches', 'q', branch)
        self.put('streams', 'branch:q', {'id': 'branch:q', 'channel': 'branch', 'started_at': 1, 'prompt_snapshot': {'branch': branch}})

        execute(self.workspace, {'op': 'course.status'})

        self.assertEqual(self.stored_version(), migrations.VERSION)
        expected = {'id': 'a', 'concept_id': 'a', 'title': 'States', 'status': 'completed', 'text': 'Lesson text', 'source_refs': lesson['source_refs']}
        self.assertEqual(execute(self.workspace, {'op': 'branch.read', 'id': 'q'})['branch']['selected_lecture'], expected)
        turn = execute(self.workspace, {'op': 'stream.read', 'id': 'branch:q'})['turn']
        self.assertEqual(turn['prompt_snapshot']['branch']['selected_lecture'], expected)

    def test_a_course_built_before_chapters_becomes_one_chapter(self):
        self.raw("DELETE FROM documents WHERE namespace='course' AND key='schema'")
        self.put('curriculum', 'model', {'concepts': [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B'}], 'route': ['a', 'b'], 'coverage': []})
        model = execute(self.workspace, {'op': 'curriculum.view'})
        self.assertEqual(model['chapters'], [{'id': 'course', 'title': 'Quantum', 'concept_ids': ['a', 'b']}])
        self.assertEqual(model['route'], ['a', 'b'])

    def test_assessments_made_before_the_review_schedule_are_dated_by_their_practice_turn(self):
        import json
        from guided_learning.store import Store
        self.put('course', 'schema', {'version': 3})
        practice = {'id': 'practice-evidence:practice-1', 'concept_id': 'a', 'kind': 'independent', 'outcome': 'passed', 'assessment_id': 'practice-feedback:practice-1'}
        chat = {'id': 'assessment-7a', 'concept_id': 'a', 'kind': 'independent', 'outcome': 'passed', 'assessment_id': 'teacher-feedback-7a'}
        hint = {'id': 'practice-feedback-help:practice-1', 'concept_id': 'a', 'kind': 'hint', 'interaction_id': 'practice-feedback:practice-1'}
        for item in (practice, chat, hint):
            self.put('evidence', item['id'], item)
        self.put('streams', 'practice-1', {'id': 'practice-1', 'channel': 'practice', 'started_at': 1700000000.5})

        execute(self.workspace, {'op': 'course.status'})

        self.assertEqual(self.stored_version(), migrations.VERSION)
        stored = {json.loads(v)['id']: json.loads(v) for (v,) in self.raw("SELECT value FROM documents WHERE namespace='evidence'")}
        self.assertEqual(stored[practice['id']], {**practice, 'assessed_at': 1700000000.5})
        self.assertEqual(stored[chat['id']], chat, 'an assessment with no practice turn stays undated')
        self.assertEqual(stored[hint['id']], hint, 'only assessments are dated')
        store = Store(self.workspace)
        try:
            migrations.date_assessments(store)  # idempotent on an already migrated course
            self.assertEqual(store.get('evidence', practice['id'])['assessed_at'], 1700000000.5)
        finally:
            store.db.close()

    def test_recaps_and_their_questions_move_to_the_chapter_from_a_version_4_course(self):
        import json
        from guided_learning.store import Store
        execute(self.workspace, {'op': 'curriculum.outline', 'chapters': [{'id': 'one', 'title': 'States'}]})
        execute(self.workspace, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B'}]})
        self.put('course', 'schema', {'version': 4})
        recap = {'id': 'recap:1', 'concept_id': 'b', 'channel': 'mainline', 'status': 'completed', 'started_at': 1,
                 'prompt_snapshot': {'context': {'concept': {'id': 'b'}, 'chapter': {'id': 'one', 'title': 'States', 'concept_ids': ['a', 'b']}}}}
        moved = {'id': 'recap:2', 'concept_id': 'gone', 'channel': 'mainline', 'status': 'completed', 'started_at': 2}
        lesson = {'id': 'lesson-1', 'concept_id': 'b', 'channel': 'mainline', 'status': 'completed', 'started_at': 0}
        job = {'id': 'practice-1', 'concept_id': 'b', 'action': 'generate', 'purpose': 'recap', 'processed': True}
        tasks = [{'id': f'practice-1:{i}', 'concept_id': 'b', 'question': f'Q{i}', 'origin': 'recap', 'source_refs': [],
                  'status': 'pending', 'history': [], 'tests_concept_ids': tests} for i, tests in enumerate((['a', 'b'], ['b']))]
        orphan = {'id': 'practice-2:0', 'concept_id': 'gone', 'question': 'Q', 'origin': 'recap', 'source_refs': [], 'status': 'pending',
                  'history': [], 'tests_concept_ids': ['gone']}
        exercise = {'id': 'practice-3:0', 'concept_id': 'b', 'question': 'E', 'origin': 'self_created', 'source_refs': [], 'status': 'pending', 'history': []}
        for turn in (recap, moved, lesson):
            self.put('streams', turn['id'], turn)
        self.put('practice_jobs', job['id'], job)
        for task in (*tasks, orphan, exercise):
            self.put('practice_tasks', task['id'], task)

        execute(self.workspace, {'op': 'course.status'})

        self.assertEqual(self.stored_version(), migrations.VERSION)
        stored = lambda ns: {json.loads(v)['id']: json.loads(v) for (v,) in self.raw('SELECT value FROM documents WHERE namespace=?', ns)}
        turns, jobs, migrated = stored('streams'), stored('practice_jobs'), stored('practice_tasks')
        self.assertEqual(turns['recap:1'], {**recap, 'chapter_id': 'one'}, 'owned by the chapter, still anchored to its last section')
        self.assertEqual(turns['recap:2'], moved, 'a recap whose section left every chapter stays anchored to it')
        self.assertEqual(turns['lesson-1'], lesson)
        self.assertEqual(jobs['practice-1'], {**job, 'purpose': 'chapter_quiz', 'chapter_id': 'one', 'quiz_id': 'practice-1', 'earlier': []})
        for task in tasks:
            self.assertEqual(migrated[task['id']], {**task, 'origin': 'chapter_quiz', 'chapter_id': 'one', 'quiz_id': 'practice-1', 'set_id': 'practice-1'},
                             'and, from version 6, a question of the review set the quiz became')
        self.assertEqual(migrated[orphan['id']], {**orphan, 'origin': 'chapter_quiz'})
        self.assertEqual(migrated[exercise['id']], exercise)
        store = Store(self.workspace)
        try:
            migrations.chapter_owned_recaps(store)  # idempotent on an already migrated course
            self.assertEqual({t['id']: t for t in store.list('practice_tasks')}, migrated)
            self.assertEqual({t['id']: t for t in store.list('streams')}, turns)
            self.assertEqual({j['id']: j for j in store.list('practice_jobs')}, jobs)
        finally:
            store.db.close()

    def test_scheduled_reviews_and_quizzes_become_review_sets_from_a_version_5_course(self):
        import json
        from datetime import datetime
        from guided_learning.store import Store
        execute(self.workspace, {'op': 'curriculum.outline', 'chapters': [{'id': 'one', 'title': 'States'}]})
        execute(self.workspace, {'op': 'curriculum.chapter.save', 'chapter_id': 'one', 'concepts': [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B'}]})
        self.put('course', 'schema', {'version': 5})
        self.put('course', 'preferences', {'language': 'zh-CN', 'daily_reviews': 8})
        self.put('review_postponements', 'a', {'concept_id': 'a', 'at': 1})
        noon = datetime(2026, 10, 1, 12).timestamp()
        # Two reviews started the same day, one the next day still being written when the old Throughline closed.
        for name, started in (('r1', noon), ('r2', noon + 3600), ('r3', noon + 86400)):
            self.put('streams', name, {'id': name, 'channel': 'practice', 'status': 'completed', 'started_at': started})
            self.put('practice_jobs', name, {'id': name, 'concept_id': 'a', 'action': 'generate', 'purpose': 'review', 'processed': name != 'r3'})
        for name in ('r1', 'r2'):
            self.put('practice_tasks', name + ':0', {'id': name + ':0', 'concept_id': 'a', 'question': name, 'origin': 'review', 'source_refs': [],
                                                    'status': 'attempted', 'history': [{'action': 'assess', 'outcome': 'passed'}]})
        quiz = {'id': 'q:0', 'concept_id': 'b', 'question': 'Q', 'origin': 'chapter_quiz', 'chapter_id': 'one', 'quiz_id': 'q',
                'tests_concept_ids': ['a'], 'source_refs': [], 'status': 'pending', 'history': [], 'created_at': 5}
        self.put('practice_tasks', quiz['id'], quiz)
        evidence = {'id': 'e', 'concept_id': 'a', 'kind': 'retest_passed', 'outcome': 'passed', 'assessment_id': 'i', 'assessed_at': noon}
        self.put('evidence', 'e', evidence)

        execute(self.workspace, {'op': 'course.status'})

        self.assertEqual(self.stored_version(), migrations.VERSION)
        stored = lambda ns: {json.loads(v)['id'] if 'id' in json.loads(v) else k: json.loads(v)
                             for (k, v) in self.raw('SELECT key, value FROM documents WHERE namespace=?', ns)}
        sets, tasks, jobs = stored('review_sets'), stored('practice_tasks'), stored('practice_jobs')
        first, second = 'migrated-review:2026-10-01', 'migrated-review:2026-10-02'
        self.assertEqual(sets[first], {'id': first, 'kind': 'for_me', 'created_at': noon}, 'one set per day, dated by its first review')
        self.assertEqual(sets[second]['created_at'], noon + 86400)
        self.assertEqual(sets['q'], {'id': 'q', 'kind': 'chapter_quiz', 'chapter_id': 'one', 'scope': {'chapter_ids': ['one']}, 'created_at': 5})
        self.assertEqual({t['id']: t['set_id'] for t in tasks.values()}, {'r1:0': first, 'r2:0': first, 'q:0': 'q'})
        self.assertEqual((tasks['r1:0']['tests_concept_ids'], tasks['r1:0']['kind']), (['a'], 'apply'))
        self.assertEqual(jobs['r3']['set_id'], second, 'a review still being written finishes into its set')
        self.assertEqual(stored('review_postponements'), {})
        self.assertEqual(stored('course')['preferences'], {'language': 'zh-CN'})
        self.assertEqual(stored('evidence')['e'], evidence)
        listed = execute(self.workspace, {'op': 'review.sets'})['sets']
        self.assertEqual({s['id']: (s['answered'], s['open']) for s in listed}, {first: (2, False), second: (0, False), 'q': (0, True)})
        store = Store(self.workspace)
        try:
            migrations.review_sets(store)  # idempotent on an already migrated course
            self.assertEqual({t['id']: t for t in store.list('practice_tasks')}, tasks)
            self.assertEqual({s['id']: s for s in store.list('review_sets')}, sets)
        finally:
            store.db.close()

    def test_a_course_from_a_newer_throughline_is_refused_and_listed_with_the_reason(self):
        self.put('course', 'schema', {'version': migrations.VERSION + 1})
        with self.assertRaises(OperationError) as raised:
            execute(self.workspace, {'op': 'course.status'})
        self.assertEqual(raised.exception.code, 'course_too_new')
        listed = library.list_courses(self.workspace.parent)
        self.assertIn('newer version of Throughline', listed[0]['error'])
        self.assertEqual(self.stored_version(), migrations.VERSION + 1, 'an older app never rewrites a newer course')


if __name__ == '__main__':
    unittest.main()
