"""Every stored course format still opens (ADR 0007): each fixture in tests/fixtures/courses is a course a learner left
at that format, written with the code of the time.

format-7 and later are written by tests/fixtures/make_course.py. Formats 1 to 6 predate it and were written once, from
an archive of the last commit at which each format was current, by a copy of make_course.py adapted to what that code
had: format 1 at cf6a9a14 (a route without chapters), 2 at f0224b6a, 3 at afabc559, 4 at 14928a45 (spaced review and
chapter recap questions), 5 at e8d61994 (stepped lessons, course memory, chapter quiz, spaced review) and 6 at bc79ef74
(review sets). Formats 1 to 4 have no stepped lessons or course memory, and their assessments are passed / needs_work.
"""
import hashlib
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from guided_learning import migrations
from guided_learning.api import execute
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings
from tests.fixtures.make_course import NOTES

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'courses'
PLACEHOLDER = '@COURSE@'
# Learning records no migration may lose.
KEPT = ('sources', 'streams', 'interactions', 'lessons', 'web_branches', 'annotations', 'practice_tasks', 'evidence', 'memory')
# Formats before stepped lessons and course memory hold no `lessons` or `memory` records.
EARLY = ('lessons', 'memory')


class Idle:
    def run(self, prompt, cwd, emit, cancel, images=None):
        cancel.wait(3)


def load(fixture, course, stored=None):
    """The fixture as a course folder at `course`, its stored paths pointing into that folder (or into `stored`), with
    the learner's notes and the saved copy of them that the course reads its source from."""
    course.mkdir(parents=True)
    path = json.dumps(str(stored or course))[1:-1].replace("'", "''")  # inside JSON inside an SQL string
    db = sqlite3.connect(course / 'course.sqlite3')
    try:
        db.executescript(fixture.read_text(encoding='utf-8').replace(PLACEHOLDER, path))
        sources = [json.loads(value) for (value,) in db.execute("SELECT value FROM documents WHERE namespace='sources'")]
    finally:
        db.close()
    data = NOTES.encode('utf-8')
    (course / 'inputs').mkdir()
    (course / 'inputs' / 'notes.md').write_bytes(data)
    for source in sources:
        assert source['revision'] == hashlib.sha256(data).hexdigest(), 'every fixture registers make_course.NOTES'
        (course / 'sources' / source['id']).mkdir(parents=True)
        (course / 'sources' / source['id'] / source['revision']).write_bytes(data)


def counts(course):
    db = sqlite3.connect(course / 'course.sqlite3')
    try:
        return dict(db.execute('SELECT namespace, count(*) FROM documents GROUP BY namespace').fetchall())
    finally:
        db.close()


def stored_version(course):
    """The course's format; a course without `course/schema` is format 1."""
    db = sqlite3.connect(course / 'course.sqlite3')
    try:
        rows = db.execute("SELECT value FROM documents WHERE namespace='course' AND key='schema'").fetchall()
        return json.loads(rows[0][0])['version'] if rows else 1
    finally:
        db.close()


def fixtures():
    found = sorted(FIXTURES.glob('format-*.sql'), key=lambda p: int(re.match(r'format-(\d+)\.sql$', p.name)[1]))
    return [(int(re.match(r'format-(\d+)\.sql$', p.name)[1]), p) for p in found]


class CourseFixtures(unittest.TestCase):
    def test_the_current_format_has_a_fixture(self):
        self.assertTrue((FIXTURES / f'format-{migrations.VERSION}.sql').is_file(),
                        f'No course fixture for format {migrations.VERSION}. After adding a migration, run '
                        f'.venv/bin/python -m tests.fixtures.make_course and commit tests/fixtures/courses/format-{migrations.VERSION}.sql')

    def test_every_format_has_a_fixture(self):
        self.assertEqual([format for format, _ in fixtures()], list(range(1, migrations.VERSION + 1)),
                         'docs/stability.md: every format has a fixture course that each later version is tested against')

    def test_every_fixture_opens_with_its_records(self):
        found = fixtures()
        self.assertTrue(found)
        for format, fixture in found:
            with self.subTest(fixture.name), tempfile.TemporaryDirectory() as scratch:
                self.check(format, fixture, Path(scratch).resolve())

    def check(self, format, fixture, root):
        course = root / 'library' / 'quantum'
        load(fixture, course)
        self.assertEqual(stored_version(course), format, 'the fixture is stored at the format its name says')
        before = counts(course)
        kept = [n for n in KEPT if format >= 5 or n not in EARLY]
        self.assertTrue(all(before.get(name) for name in kept), f'the fixture holds every kind of record of its format: {before}')

        app = create_app(course, runner=Idle(), settings=TeacherSettings(root / 'settings.json'), library_root=course.parent)
        with TestClient(app, base_url='http://127.0.0.1:8765') as client:
            responses = {path: client.get(path) for path in ('/api/state', '/api/review', '/api/library')}
            for path, response in responses.items():
                self.assertEqual(response.status_code, 200, f'{path}: {response.text}')
            state, review, library = (r.json() for r in responses.values())
            [source] = state['sources']
            opened = client.get(f"/api/sources/{source['id']}/{source['revision']}/line-2")
            self.assertEqual(opened.status_code, 200, opened.text)
            self.assertIn('Two paths reach the same detector', opened.text, 'the learner opens a cited passage')

        self.assertEqual(stored_version(course), migrations.VERSION)
        if format < migrations.VERSION:
            self.assertTrue((course / 'backups' / f'course-format-{format}.sqlite3').is_file(), 'the course is backed up before migrating')
        after = counts(course)
        self.assertEqual({n: after.get(n) for n in KEPT}, {n: before.get(n) for n in KEPT}, 'no learning record is lost')

        # The course and its route.
        self.assertEqual(state['course']['title'], 'Introductory Quantum Mechanics')
        self.assertEqual(state['position']['concept_id'], 'states')
        concepts = {c['id']: c['title'] for c in state['curriculum']['concepts']}
        self.assertEqual([concepts[c] for c in state['curriculum']['route']], ['Adding path amplitudes', 'States and global phase', 'Measurement outcomes'])
        chapters = state['curriculum']['chapters']
        if format == 1:
            # A route saved without chapters became one chapter titled after the course (ADR 0006).
            self.assertEqual([(c['id'], c['title'], c['concept_ids']) for c in chapters],
                             [('course', 'Introductory Quantum Mechanics', ['paths', 'states', 'outcomes'])])
        else:
            self.assertEqual([(c['id'], c['concept_ids']) for c in chapters], [('superposition', ['paths', 'states']), ('measurement', ['outcomes'])])

        # The source, readable through the operation Codex uses.
        self.assertEqual(len(state['sources']), before['sources'])
        [source] = state['sources']
        units = {u['id']: u['text'] for u in execute(course, {'op': 'source.read', 'source_id': source['id']})['units']}
        self.assertEqual(units['line-2'], 'Two paths reach the same detector, each with a complex amplitude.')

        # The lesson the learner read, its side question and notes.
        lesson = next(t for t in state['turns'] if t['channel'] == 'mainline' and t['status'] == 'completed' and t.get('concept_id') == 'paths'
                      and not t['id'].startswith('recap:'))
        self.assertIn('Each path carries a complex amplitude', lesson['text'])
        self.assertEqual(len(state['lessons']), before.get('lessons', 0))
        if format >= 5:
            [stepped] = [l for l in state['lessons'] if l['concept_id'] == 'paths']
            self.assertEqual(len(stepped['steps']), 2, 'the stepped lesson keeps both steps')
        self.assertEqual(len(state['questions']), before['web_branches'])
        [question] = state['questions']
        self.assertEqual(question['question'], 'Why is the cross term 2 Re(a* b)?')
        self.assertEqual(question['selection'], 'a complex amplitude')
        self.assertEqual([r['question'] for r in question['replies']], ['And when both amplitudes are real?'], 'the side question keeps its follow-up')
        self.assertEqual(question['selected_lecture']['id'], lesson['id'])
        selected = execute(course, {'op': 'branch.read', 'id': question['id']})['branch']['selected_lecture']
        self.assertIn('Each path carries a complex amplitude', selected['text'])
        stored = sqlite3.connect(course / 'course.sqlite3')
        try:
            branches = [json.loads(v) for (v,) in stored.execute("SELECT value FROM documents WHERE namespace='web_branches'")]
            turns = [json.loads(v) for (v,) in stored.execute("SELECT value FROM documents WHERE namespace='streams'")]
        finally:
            stored.close()
        self.assertFalse([t['id'] for t in turns if 'prompt_snapshot' in t], 'a turn\'s frozen prompt is stored apart from it (ADR 0018)')
        self.assertEqual(after.get('stream_snapshots'), len(turns))
        self.assertFalse([b['id'] for b in branches if 'prompt_snapshot' in (b.get('selected_lecture') or {})],
                         'a side question keeps an excerpt of its lesson, not its prompt')
        self.assertEqual(len(state['annotations']), before['annotations'])
        self.assertEqual(sorted((a['kind'], a.get('note') or '') for a in state['annotations']),
                         [('bookmark', ''), ('highlight', ''), ('note', 'Compare with classical intensities.')])
        self.assertTrue(any(t['channel'] == 'mainline' and t['status'] == 'completed' and t['text'] for t in state['turns']))

        # The learner's answers and their assessment.
        [exercise] = [t for t in state['practice']['tasks'] if t['concept_id'] == 'paths' and t['origin'] == 'self_created']
        assessed = [h for h in exercise['history'] if h.get('action') == 'assess']
        self.assertTrue(assessed and all(h.get('answer', '').startswith(('P = (1 + cos phi)/2', '(a) P = (1 + cos phi)/2')) for h in assessed), exercise['history'])
        self.assertIn('hint', [h.get('action') for h in exercise['history']])
        history = execute(course, {'op': 'evidence.view', 'concept_id': 'paths'})['history']
        graded = [e for e in history if e.get('exercise_id') == exercise['id'] and e.get('assessment_id')]
        self.assertEqual(len(graded), len(assessed), 'every assessment of the exercise is kept as evidence')
        for item in graded:
            self.assertTrue(item['answer_id'] and item['outcome'])
            self.assertIsInstance(item.get('assessed_at'), (int, float), 'an assessment made in the app is dated (ADR 0008)')
        [deferred] = [t for t in state['practice']['tasks'] if t['concept_id'] == 'states' and t['origin'] == 'self_created']
        self.assertEqual(deferred['status'], 'deferred')

        # Later records: chapter recaps, review and course memory, as far as the format had them.
        if format >= 2:
            [recap] = [t for t in state['turns'] if t['id'].startswith('recap:')]
            self.assertEqual(recap['status'], 'completed')
        if format >= 4:
            self.assertEqual({s['kind'] for s in review['sets']}, {'for_me', 'chapter_quiz'})
            quiz = next(s for s in review['sets'] if s['kind'] == 'chapter_quiz')
            self.assertEqual(quiz['chapter_id'], 'superposition')
            self.assertTrue(review['tasks'])
        if format >= 5:
            self.assertTrue(state['practice']['tasks'])
            self.assertTrue({e['kind'] for e in state['memory']} >= {'preference', 'taught_term', 'difficulty'})
        else:
            self.assertEqual(state['memory'], [])
        [listed] = library['courses']
        self.assertNotIn('error', listed)
        self.assertEqual(listed['concepts'], 3)


if __name__ == '__main__':
    unittest.main()
