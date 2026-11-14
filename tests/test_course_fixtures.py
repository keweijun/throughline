"""Every stored course format still opens (ADR 0007): each fixture in tests/fixtures/courses is a course a learner left
at that format, written by tests/fixtures/make_course.py with the code of the time."""
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from guided_learning import migrations
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'courses'
PLACEHOLDER = '@COURSE@'
# Learning records no migration may lose.
KEPT = ('sources', 'streams', 'interactions', 'lessons', 'web_branches', 'annotations', 'practice_tasks', 'evidence', 'memory')


class Idle:
    def run(self, prompt, cwd, emit, cancel, images=None):
        cancel.wait(3)


def load(fixture, course):
    """The fixture as a course folder at `course`, its stored paths pointing into that folder."""
    course.mkdir(parents=True)
    path = json.dumps(str(course))[1:-1].replace("'", "''")  # inside JSON inside an SQL string
    db = sqlite3.connect(course / 'course.sqlite3')
    try:
        db.executescript(fixture.read_text(encoding='utf-8').replace(PLACEHOLDER, path))
    finally:
        db.close()


def counts(course):
    db = sqlite3.connect(course / 'course.sqlite3')
    try:
        return dict(db.execute('SELECT namespace, count(*) FROM documents GROUP BY namespace').fetchall())
    finally:
        db.close()


def stored_version(course):
    db = sqlite3.connect(course / 'course.sqlite3')
    try:
        [(value,)] = db.execute("SELECT value FROM documents WHERE namespace='course' AND key='schema'").fetchall()
        return json.loads(value)['version']
    finally:
        db.close()


class CourseFixtures(unittest.TestCase):
    def test_the_current_format_has_a_fixture(self):
        self.assertTrue((FIXTURES / f'format-{migrations.VERSION}.sql').is_file(),
                        f'No course fixture for format {migrations.VERSION}. After adding a migration, run '
                        f'.venv/bin/python -m tests.fixtures.make_course and commit tests/fixtures/courses/format-{migrations.VERSION}.sql')

    def test_every_fixture_opens_with_its_records(self):
        fixtures = sorted(FIXTURES.glob('format-*.sql'))
        self.assertTrue(fixtures)
        for fixture in fixtures:
            with self.subTest(fixture.name), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch).resolve()
                course = root / 'library' / 'quantum'
                load(fixture, course)
                format = int(re.match(r'format-(\d+)\.sql$', fixture.name)[1])
                self.assertEqual(stored_version(course), format, 'the fixture is stored at the format its name says')
                before = counts(course)
                self.assertTrue(all(before.get(name) for name in KEPT), f'the fixture holds every kind of record: {before}')

                app = create_app(course, runner=Idle(), settings=TeacherSettings(root / 'settings.json'), library_root=course.parent)
                with TestClient(app, base_url='http://127.0.0.1:8765') as client:
                    responses = {path: client.get(path) for path in ('/api/state', '/api/review', '/api/library')}
                    for path, response in responses.items():
                        self.assertEqual(response.status_code, 200, f'{path}: {response.text}')
                    state, review, library = (r.json() for r in responses.values())

                self.assertEqual(stored_version(course), migrations.VERSION)
                after = counts(course)
                self.assertEqual({n: after.get(n) for n in KEPT}, {n: before[n] for n in KEPT}, 'no learning record is lost')
                self.assertEqual(state['course']['title'], 'Introductory Quantum Mechanics')
                self.assertEqual(state['position']['concept_id'], 'states')
                self.assertEqual([c['id'] for c in state['curriculum']['chapters']], ['superposition', 'measurement'])
                self.assertEqual(len(state['sources']), before['sources'])
                self.assertEqual(len(state['lessons']), before['lessons'])
                self.assertEqual(len(state['questions']), before['web_branches'])
                self.assertEqual(len(state['annotations']), before['annotations'])
                self.assertTrue(state['questions'][0]['replies'], 'the side question keeps its follow-up')
                self.assertTrue(any(t['channel'] == 'mainline' and t['status'] == 'completed' and t['text'] for t in state['turns']))
                self.assertTrue(state['practice']['tasks'])
                self.assertTrue({e['kind'] for e in state['memory']} >= {'preference', 'taught_term', 'difficulty'})
                self.assertTrue(review['sets'] and review['tasks'])
                [listed] = library['courses']
                self.assertNotIn('error', listed)
                self.assertEqual(listed['concepts'], 3)


if __name__ == '__main__':
    unittest.main()
