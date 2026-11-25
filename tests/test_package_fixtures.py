"""Course packages from every package format import into this version at each share level (docs/stability.md, ADR 0020).

Each tests/fixtures/packages/package-<format>-<level>.throughline was exported from the fixture course of its time by
tests/fixtures/make_packages.py. A package is imported in every way its level allows, and what it carries and leaves
out is checked against the share level table in ADR 0020. The same checks run on packages this version exports now.
"""
import json
import re
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from throughline import migrations, packages
from throughline.api import execute
from tests.test_course_fixtures import FIXTURES, load

PACKAGES = Path(__file__).resolve().parent / 'fixtures' / 'packages'
TITLES = ['Adding path amplitudes', 'States and global phase', 'Measurement outcomes']
BUILT_FOR = {'goal': 'Understand interference and measurement', 'depth': 'standard', 'focus': 'Problem solving'}
# The sender's own learning, which only a continued Everything package brings.
SENDERS = ('interactions', 'evidence', 'evidence_deferred', 'memory', 'memory_notes', 'memory_consolidations', 'annotations', 'web_branches',
           'review_sets', 'practice_jobs', 'preparation_jobs', 'preparation_payloads', 'checkpoint_receipts', 'stream_snapshots')
# Fixture records a continued course keeps exactly.
KEPT = ('sources', 'source_revisions', 'curriculum', 'streams', 'lessons', 'practice_tasks', *SENDERS)


def counts(course):
    db = sqlite3.connect(Path(course) / 'course.sqlite3')
    try:
        return dict(db.execute('SELECT namespace, count(*) FROM documents GROUP BY namespace').fetchall())
    finally:
        db.close()


def records(course, namespace):
    db = sqlite3.connect(Path(course) / 'course.sqlite3')
    try:
        return {k: json.loads(v) for k, v in db.execute('SELECT key, value FROM documents WHERE namespace=?', (namespace,))}
    finally:
        db.close()


def committed():
    found = []
    for path in sorted(PACKAGES.glob('package-*.throughline')):
        match = re.fullmatch(r'package-(\d+)-(route|lessons|everything)\.throughline', path.name)
        found.append((int(match[1]), match[2], path))
    return found


class PackageFixtures(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()

    def test_the_current_package_format_has_a_package_at_each_level(self):
        levels = {level for format, level, _ in committed() if format == packages.FORMAT}
        self.assertEqual(levels, set(packages.LEVELS), f'After raising the package format, run .venv/bin/python -m tests.fixtures.make_packages '
                                                        f'and commit tests/fixtures/packages/package-{packages.FORMAT}-*.throughline')

    def test_every_package_imports_at_its_level(self):
        found = committed()
        self.assertTrue(found)
        for format, level, package in found:
            with zipfile.ZipFile(package) as archive:
                self.assertEqual(json.loads(archive.read('manifest.json'))['level'], level)
            for mode in self.modes(level):
                with self.subTest(package.name, mode=mode):
                    self.check(package, level, mode, f'{format}-{level}-{mode}')

    def test_a_package_this_version_exports_imports_at_its_level(self):
        sender = self.home / 'sender' / 'quantum'
        load(FIXTURES / f'format-{migrations.VERSION}.sql', sender)
        self.sender = counts(sender)
        for level in packages.LEVELS:
            package = self.home / f'{level}.throughline'
            exported = packages.export(sender, package, level)
            self.assertEqual((exported['level'], exported['title'], exported['sources']), (level, 'Introductory Quantum Mechanics', 1))
            for mode in self.modes(level):
                with self.subTest(level, mode=mode):
                    self.check(package, level, mode, f'now-{level}-{mode}')

    def modes(self, level):
        return packages.MODES if level == 'everything' else ('fresh',)

    def sender_counts(self):
        """The fixture course the packages were made from, as it stands at this version."""
        if not hasattr(self, 'sender'):
            course = self.home / 'reference' / 'quantum'
            load(FIXTURES / f'format-{migrations.VERSION}.sql', course)
            execute(course, {'op': 'course.status'})
            self.sender = counts(course)
        return self.sender

    def check(self, package, level, mode, name):
        library = self.home / 'library'
        library.mkdir(exist_ok=True)
        result = packages.import_package(package, library, name=name, mode=mode)
        self.assertEqual((result['name'], result['level'], result['mode'], result['title'], result['sources']),
                         (name, level, mode, 'Introductory Quantum Mechanics', 1))
        course = Path(result['path'])
        taken = level if mode == 'continue' else ('route' if level == 'route' else 'lessons')
        op = lambda **request: execute(course, request)

        # Every level: the route as built, the sources as read, the add-ons.
        status = op(op='course.status')
        self.assertEqual(status['course']['title'], 'Introductory Quantum Mechanics')
        model = op(op='curriculum.view')
        titles = {c['id']: c['title'] for c in model['concepts']}
        self.assertEqual([titles[c] for c in model['route']], TITLES)
        self.assertEqual([(c['id'], c['concept_ids']) for c in model['chapters']], [('superposition', ['paths', 'states']), ('measurement', ['outcomes'])])
        [concept] = [c for c in model['concepts'] if c['id'] == 'paths']
        self.assertEqual(concept['exercises'][0]['question'], 'Find the probability for equal amplitudes.')
        [source] = status['sources']
        units = {u['id']: u['text'] for u in op(op='source.read', source_id=source['id'])['units']}
        self.assertEqual(units['line-2'], 'Two paths reach the same detector, each with a complex amplitude.')
        self.assertTrue((course / 'sources' / source['id'] / source['revision']).is_file(), 'the package carries the source file')
        self.assertEqual(op(op='widgets.list')['selected'], ['plot'])
        found = counts(course)
        tasks = records(course, 'practice_tasks')
        lessons = records(course, 'lessons')
        streams = records(course, 'streams')

        if taken == 'everything':
            # Continued: the course as it was left, the sender's progress and records with it.
            sender = self.sender_counts()
            self.assertEqual({n: found.get(n) for n in KEPT}, {n: sender.get(n) for n in KEPT})
            self.assertEqual(status['position']['concept_id'], 'states')
            self.assertEqual(status['profile']['goal'], BUILT_FOR['goal'])
            self.assertNotIn('imported', status)
            self.assertTrue(any(h.get('action') == 'assess' for t in tasks.values() for h in t.get('history', [])))
            self.assertTrue(any(e.get('status') == 'confirmed' for e in records(course, 'memory').values()))
            return

        # Started fresh: marked as shared, with the sender's goal as a note and nothing of their own learning.
        self.assertTrue(status.get('imported'))
        self.assertEqual(status.get('built_for'), BUILT_FOR)
        self.assertFalse(status.get('profile'), 'the sender profile stays theirs')
        self.assertFalse(status['position'], 'the recipient starts where a new course starts')
        notes = mode == 'fresh-with-notes'
        for namespace in SENDERS:
            if notes and namespace in ('annotations', 'web_branches'):
                continue
            self.assertFalse(found.get(namespace), f'{namespace} is the sender\'s and stays with them')
        if notes:
            # The sender's notes and answered questions, to read, marked as theirs.
            kept = records(course, 'annotations')
            self.assertEqual(sorted(a.get('note') or '' for a in kept.values()), ['', '', 'Compare with classical intensities.'])
            self.assertTrue(all(a.get('from_sender') for a in kept.values()))
            [question] = records(course, 'web_branches').values()
            self.assertEqual(question['question'], 'Why is the cross term 2 Re(a* b)?')
            self.assertTrue(question.get('from_sender'))

        if taken == 'route':
            # Route: no lesson or exercise; the recipient's teacher writes them.
            self.assertEqual((lessons, tasks, streams), ({}, {}, {}))
            return

        # Route and lessons: the lessons written so far and exercises without the sender's answers, feedback or status.
        self.assertEqual(sorted(l['concept_id'] for l in lessons.values()), ['paths', 'states'])
        [stepped] = [l for l in lessons.values() if l['concept_id'] == 'paths']
        self.assertEqual(len(stepped['steps']), 2, 'each step written to its end')
        self.assertTrue(stepped['steps'][0].get('check'), 'with its check question')
        written = [t for t in streams.values() if t.get('text')]
        self.assertTrue(any('Each path carries a complex amplitude' in t['text'] for t in written))
        senders_answers = ('branch:', 'reply:') if notes else ()  # kept with the side question they answer
        for turn in streams.values():
            self.assertNotIn('prompt_snapshot', turn)
            if turn['id'].startswith(senders_answers):
                continue
            self.assertFalse(turn['id'].startswith(('recap:', 'preparation-', 'practice-', 'branch:', 'reply:')), turn['id'])
            self.assertNotIn('<course-memory>', turn.get('text') or '')
        self.assertTrue(tasks, 'the exercises written so far')
        for task in tasks.values():
            self.assertNotIn(task['origin'], ('chapter_quiz', 'review'))
            self.assertFalse(task.get('history'), 'no answers, help or feedback')
            self.assertEqual(task.get('status', 'pending'), 'pending')
            self.assertNotIn('answer', task)


if __name__ == '__main__':
    unittest.main()
