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
