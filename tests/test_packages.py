import ast
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from guided_learning import images, migrations, packages
from guided_learning.api import execute
from guided_learning.store import OperationError
from support import ROOT
from tests.sample_pdf import write_pdf

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 32


class CoursePackages(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.sender = self.home / 'sender'
        self.recipient = self.home / 'recipient'
        self.recipient.mkdir()
        self.course = self.sender / 'quantum-v1'
        execute(self.course, {'op': 'course.init', 'title': 'Quantum'})
        notes = self.home / 'notes.md'
        notes.write_text('# States\nA state is a ray in Hilbert space.', encoding='utf-8')
        self.source = execute(self.course, {'op': 'source.register', 'path': str(notes)})['source']
        execute(self.course, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})
        self.image = images.save(self.course, PNG)
        self.note = execute(self.course, {'op': 'annotations.save', 'id': 'note-1', 'kind': 'note', 'concept_id': 'state', 'note': 'Rays, not vectors', 'images': [self.image]})['annotation']
        self.package = self.home / 'quantum.throughline'

    def records(self, course):
        db = sqlite3.connect(course / 'course.sqlite3')
        try:
            return {(n, k): json.loads(v) for n, k, v in db.execute('SELECT namespace, key, value FROM documents')}
        finally:
            db.close()

    def rewrite(self, change):
        """Unpack the package, let `change(folder)` edit it, and pack it again."""
        folder = self.home / 'unpacked'
        with zipfile.ZipFile(self.package) as archive:
            archive.extractall(folder)
        change(folder)
        with zipfile.ZipFile(self.package, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(folder).as_posix())

    def assertNothingImported(self):
        self.assertEqual([p.name for p in self.recipient.iterdir() if p.name != '.throughline'], [])
        self.assertEqual(list((self.recipient / '.throughline' / 'imports').glob('*')) if (self.recipient / '.throughline').exists() else [], [])

    def test_a_course_continues_where_it_was_left_on_another_computer(self):
        exported = packages.export(self.course, self.package)
        self.assertEqual((exported['level'], exported['title'], exported['sources']), ('everything', 'Quantum', 1))
        with zipfile.ZipFile(self.package) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read('manifest.json'))
        self.assertEqual(names, {'manifest.json', 'course.sqlite3', f"sources/{self.source['id']}/{self.source['revision']}", f'answer_images/{self.image}'})
        self.assertEqual((manifest['format'], manifest['level'], manifest['schema'], manifest['name']), (packages.FORMAT, 'everything', migrations.VERSION, 'quantum-v1'))
        self.assertEqual(manifest['sources'], [{'id': self.source['id'], 'revision': self.source['revision'], 'name': 'notes.md'}])

        imported = packages.import_package(self.package, self.recipient)
        course = self.recipient / 'quantum-v1'
        self.assertEqual((imported['name'], imported['title'], imported['sources']), ('quantum-v1', 'Quantum', 1))
        before, after = self.records(self.course), self.records(course)
        self.assertNotEqual(after.pop(('course', 'metadata'))['id'], before.pop(('course', 'metadata'))['id'])
        self.assertEqual(after, before)
        self.assertEqual(execute(course, {'op': 'annotations.list'})['annotations'], [self.note])
        self.assertEqual(images.path(course, self.image).read_bytes(), PNG)
        unit = execute(course, {'op': 'source.read', 'source_id': self.source['id'], 'revision': self.source['revision']})
        self.assertIn('A state is a ray in Hilbert space.', json.dumps(unit, ensure_ascii=False))
        self.assertNothingImported_staging()

    def assertNothingImported_staging(self):
        self.assertEqual(list((self.recipient / '.throughline' / 'imports').iterdir()), [])

    def test_a_moved_course_reads_its_pdf_pages_without_the_original_file(self):
        lecture = self.home / 'lecture.pdf'
        write_pdf(lecture, [['Lecture 1', 'Amplitudes add before squaring.']])
        pdf = execute(self.course, {'op': 'source.register', 'path': str(lecture)})['source']
        packages.export(self.course, self.package)
        lecture.unlink()
        course = Path(packages.import_package(self.package, self.recipient)['path'])
        unit = execute(course, {'op': 'source.read', 'source_id': pdf['id'], 'revision': pdf['revision']})
        self.assertIn('Amplitudes add before squaring.', json.dumps(unit))

    def test_names_are_made_unique_unless_one_is_asked_for(self):
        packages.export(self.course, self.package)
        self.assertEqual(packages.import_package(self.package, self.recipient)['name'], 'quantum-v1')
        self.assertEqual(packages.import_package(self.package, self.recipient)['name'], 'quantum-v1-2')
        self.assertEqual(packages.import_package(self.package, self.recipient, 'mine')['name'], 'mine')
        with self.assertRaises(OperationError) as taken:
            packages.import_package(self.package, self.recipient, 'mine')
        self.assertEqual(taken.exception.code, 'course_exists')
        with self.assertRaises(OperationError) as invalid:
            packages.import_package(self.package, self.recipient, '../escape')
        self.assertEqual(invalid.exception.code, 'invalid_course_name')

    def test_a_package_from_an_older_throughline_migrates_on_import(self):
        packages.export(self.course, self.package)

        def downgrade(folder):
            db = sqlite3.connect(folder / 'course.sqlite3')
            # Version 6 kept a turn's prompt snapshot inside the turn (ADR 0018).
            turn = {'id': 'turn-1', 'concept_id': 'state', 'channel': 'lesson', 'status': 'completed', 'text': 'Hello', 'attempts': [],
                    'prompt_snapshot': {'concept': {'id': 'state', 'title': 'States'}}}
            db.execute('INSERT INTO documents VALUES (?, ?, ?)', ('streams', 'turn-1', json.dumps(turn)))
            db.execute("UPDATE documents SET value=? WHERE namespace='course' AND key='schema'", (json.dumps({'version': 6}),))
            db.commit()
            db.close()
            manifest = json.loads((folder / 'manifest.json').read_text())
            (folder / 'manifest.json').write_text(json.dumps({**manifest, 'schema': 6}))
        self.rewrite(downgrade)

        course = Path(packages.import_package(self.package, self.recipient)['path'])
        records = self.records(course)
        self.assertEqual(records[('course', 'schema')], {'version': migrations.VERSION})
        self.assertNotIn('prompt_snapshot', records[('streams', 'turn-1')])
        self.assertEqual(records[('stream_snapshots', 'turn-1')]['prompt_snapshot'], {'concept': {'id': 'state', 'title': 'States'}})

    def test_packages_from_a_newer_throughline_are_refused_before_unpacking(self):
        packages.export(self.course, self.package)
        for field, value, code in (('schema', migrations.VERSION + 1, 'course_too_new'), ('format', packages.FORMAT + 1, 'package_too_new'),
                                   ('level', 'route', 'package_too_new')):
            original = self.package.read_bytes()
            self.rewrite(lambda folder: (folder / 'manifest.json').write_text(json.dumps({**json.loads((folder / 'manifest.json').read_text()), field: value})))
            with self.assertRaises(OperationError) as refused:
                packages.import_package(self.package, self.recipient)
            self.assertEqual(refused.exception.code, code)
            self.assertNothingImported()
            self.package.write_bytes(original)

    def test_unexpected_entries_refuse_the_package(self):
        packages.export(self.course, self.package)
        for name in ('../escape.txt', '/absolute.txt', 'sources/../../escape', 'notes.txt', 'sources/src-1/not-a-revision'):
            with self.subTest(name=name):
                original = self.package.read_bytes()
                with zipfile.ZipFile(self.package, 'a') as archive:
                    archive.writestr(name, 'x')
                with self.assertRaises(OperationError) as refused:
                    packages.import_package(self.package, self.recipient)
                self.assertEqual(refused.exception.code, 'invalid_package')
                self.assertNothingImported()
                self.assertFalse((self.home / 'escape.txt').exists())
                self.package.write_bytes(original)

    def test_files_that_do_not_match_their_hash_refuse_the_package(self):
        packages.export(self.course, self.package)
        self.rewrite(lambda folder: (folder / 'sources' / self.source['id'] / self.source['revision']).write_text('tampered'))
        with self.assertRaises(OperationError) as refused:
            packages.import_package(self.package, self.recipient)
        self.assertEqual(refused.exception.code, 'invalid_package')
        self.assertNothingImported()

    def test_a_database_that_is_not_a_course_refuses_the_package(self):
        packages.export(self.course, self.package)
        original = self.package.read_bytes()

        def as_view(folder):
            db = sqlite3.connect(folder / 'course.sqlite3')
            db.executescript("ALTER TABLE documents RENAME TO kept; CREATE VIEW documents AS SELECT * FROM kept;")
            db.close()
        for change in (lambda folder: (folder / 'course.sqlite3').write_bytes(b'not a database'), as_view):
            self.rewrite(change)
            with self.assertRaises(OperationError) as refused:
                packages.import_package(self.package, self.recipient)
            self.assertEqual(refused.exception.code, 'invalid_package')
            self.assertNothingImported()
            self.package.write_bytes(original)
        with self.assertRaises(OperationError) as refused:
            packages.import_package(self.home / 'notes.md', self.recipient)
        self.assertEqual(refused.exception.code, 'invalid_package')

    def test_the_commands_export_and_import_by_course_name(self):
        env = {**os.environ, 'GUIDED_LEARNING_HOME': str(self.sender)}
        run = lambda *args: subprocess.run([sys.executable, '-m', 'guided_learning', *args], capture_output=True, text=True, encoding='utf-8',
                                           cwd=ROOT, env=env, timeout=60)
        exported = run('export', 'quantum-v1', '--out', str(self.package))
        self.assertEqual(exported.returncode, 0, exported.stdout + exported.stderr)
        self.assertEqual(json.loads(exported.stdout)['result']['path'], str(self.package.resolve()))
        imported = run('import', str(self.package), '--name', 'copy')
        self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
        self.assertEqual(json.loads(imported.stdout)['result']['name'], 'copy')
        self.assertTrue((self.sender / 'copy' / 'course.sqlite3').is_file())
        refused = run('import', str(self.package), '--name', 'copy')
        self.assertEqual((refused.returncode, json.loads(refused.stdout)['error']['code']), (1, 'course_exists'))


class MovedSources(unittest.TestCase):
    """A file registered from a new path keeps the source of the same content whose file is gone (ADR 0020)."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.course = self.home / 'course'
        execute(self.course, {'op': 'course.init', 'title': 'Quantum'})
        self.first = self.home / 'first' / 'lecture.pdf'
        self.first.parent.mkdir()
        write_pdf(self.first, [['Lecture 1', 'Amplitudes add before squaring.']])
        self.source = execute(self.course, {'op': 'source.register', 'path': str(self.first)})['source']
        self.second = self.home / 'second' / 'lecture.pdf'
        self.second.parent.mkdir()

    def sources(self):
        return execute(self.course, {'op': 'course.status'})['sources']

    def test_a_recipient_adding_their_own_copy_keeps_the_imported_source(self):
        package, library = self.home / 'q.throughline', self.home / 'library'
        library.mkdir()
        packages.export(self.course, package)
        self.second.write_bytes(self.first.read_bytes())
        self.first.unlink()  # the sender's folder does not exist on the recipient's computer
        course = Path(packages.import_package(package, library)['path'])
        registered = execute(course, {'op': 'source.register', 'path': str(self.second)})
        self.assertEqual(registered['source']['id'], self.source['id'])
        self.assertEqual(registered['moved_from'], str(self.first.resolve()))
        self.assertEqual([(s['id'], s['path'], s['revision']) for s in execute(course, {'op': 'course.status'})['sources']],
                         [(self.source['id'], str(self.second.resolve()), self.source['revision'])])

    def test_a_moved_file_keeps_its_source(self):
        os.replace(self.first, self.second)
        registered = execute(self.course, {'op': 'source.register', 'path': str(self.second)})
        self.assertEqual(registered['source']['id'], self.source['id'])
        self.assertEqual([s['path'] for s in self.sources()], [str(self.second.resolve())])

    def test_two_copies_both_present_stay_two_sources(self):
        self.second.write_bytes(self.first.read_bytes())
        registered = execute(self.course, {'op': 'source.register', 'path': str(self.second)})
        self.assertNotEqual(registered['source']['id'], self.source['id'])
        self.assertNotIn('moved_from', registered)
        self.assertEqual(len(self.sources()), 2)

    def test_a_changed_file_at_a_new_path_is_a_new_source(self):
        self.first.unlink()
        write_pdf(self.second, [['Lecture 1, revised', 'Amplitudes add before squaring.']])
        registered = execute(self.course, {'op': 'source.register', 'path': str(self.second)})
        self.assertNotEqual(registered['source']['id'], self.source['id'])
        self.assertEqual(len(self.sources()), 2)


STORE_METHODS = {'get', 'put', 'list', 'matching', 'delete', 'shared', 'digest'}


def used_namespaces():
    """Every namespace the package's code reads or writes through a store, with the course namespace's keys."""
    namespaces, course_keys = set(), set()
    for path in (ROOT / 'guided_learning').rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        constants = {node.targets[0].id: node.value.value for node in tree.body
                     if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                     and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in STORE_METHODS and node.args):
                continue
            receiver = node.func.value
            if not (isinstance(receiver, ast.Name) and receiver.id == 'store' or isinstance(receiver, ast.Attribute) and receiver.attr == 'store'):
                continue
            first = node.args[0]
            namespace = first.value if isinstance(first, ast.Constant) else constants.get(first.id) if isinstance(first, ast.Name) else None
            if isinstance(namespace, str):
                namespaces.add(namespace)
                if namespace == 'course' and len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    course_keys.add(node.args[1].value)
    return namespaces, course_keys


class ShareLevels(unittest.TestCase):
    def test_every_namespace_the_code_uses_has_a_share_level(self):
        namespaces, course_keys = used_namespaces()
        self.assertGreater(len(namespaces), 20)  # the scan still finds the store calls
        self.assertEqual(sorted(namespaces - set(packages.NAMESPACES) - {'course'}), [], 'Add these to packages.NAMESPACES (ADR 0020)')
        self.assertEqual(sorted(course_keys - set(packages.COURSE_KEYS)), [], 'Add these to packages.COURSE_KEYS (ADR 0020)')
        self.assertLessEqual(set(packages.NAMESPACES.values()) | set(packages.COURSE_KEYS.values()), set(packages.LEVELS))


if __name__ == '__main__':
    unittest.main()
