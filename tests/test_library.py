import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from guided_learning import api, library, sources
from guided_learning.api import execute
from guided_learning.store import OperationError, Store
from guided_learning.server import Host, create_app
from guided_learning.server import host as host_module
from guided_learning.server.builds import ChapterBuilds
from guided_learning.server.features import Preparation
from guided_learning.server.settings import TeacherSettings
from support import ROOT


def course(path, title):
    execute(path, {'op': 'course.init', 'title': title})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})


def cli(home, *args, stdin='', **extra):
    env = {**os.environ, **extra, 'GUIDED_LEARNING_HOME': str(home), 'GUIDED_LEARNING_SKILLS_DIR': str(Path(home) / '.skills'),
           'XDG_DATA_HOME': str(Path(home) / '.xdg'), 'APPDATA': str(Path(home) / '.appdata')}
    return subprocess.run([sys.executable, '-m', 'guided_learning', *args], input=stdin, text=True, encoding='utf-8',
                          capture_output=True, cwd=ROOT, env=env, timeout=60)


def written_ago(path, seconds):
    """Date the course database's files back, as for a course last written that long ago."""
    for file in (Path(path) / 'course.sqlite3', Path(path) / 'course.sqlite3-wal'):
        if file.exists():
            then = file.stat().st_mtime - seconds
            os.utime(file, (then, then))


@contextmanager
def watched(root, also=()):
    """The app on a library holding the course `alpha`, open, and the courses `also`, all last written a while ago; with
    what the app publishes and `polls()`, which returns once the library watcher has made a whole poll that began after
    the call. The host's preparation and chapter builds do not run: they write to the course and publish on their own
    schedule, which a slow computer stretches into the test's."""
    for name in ('alpha', *also):
        course(Path(root) / name, name.title())
    config = tempfile.TemporaryDirectory()
    with config, mock.patch.object(Preparation, 'start'), mock.patch.object(ChapterBuilds, 'start'):
        app = create_app(Path(root) / 'alpha', runner=Idle(), settings=TeacherSettings(Path(config.name) / 's.json'),
                         library_root=root, watch_interval=0.01)
        for name in ('alpha', *also):
            written_ago(Path(root) / name, 10)
        courses = app.state.courses
        events = []
        courses.events.publish = events.append
        done = threading.Condition()
        count = [0]
        fingerprints = courses._fingerprints

        def counted():  # the watcher's poll begins here, then announces what it found
            with done:
                count[0] += 1
                done.notify_all()
            return fingerprints()
        courses._fingerprints = counted

        def polls():
            # The poll under way may have looked before the call; the next one begins after it, and has announced
            # what it found once the one after that begins.
            with done:
                target = count[0] + 2
                if not done.wait_for(lambda: count[0] >= target, timeout=60):
                    raise AssertionError('the library watcher stopped polling')
        with TestClient(app, base_url='http://127.0.0.1:8765'):
            yield app, events, polls


class Idle:
    def run(self, prompt, cwd, emit, cancel):
        cancel.wait(3)


class CourseLibrary(unittest.TestCase):
    def test_courses_by_name_and_listing(self):
        with tempfile.TemporaryDirectory() as home:
            created = cli(home, '--course', 'quantum-v1', stdin=json.dumps({'op': 'course.init', 'title': 'Quantum'}))
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertTrue((Path(home) / 'quantum-v1' / 'course.sqlite3').is_file())
            rejected = cli(home, '--course', '../escape', stdin=json.dumps({'op': 'course.status'}))
            self.assertEqual(json.loads(rejected.stdout)['error']['code'], 'invalid_course_name')
            listed = json.loads(cli(home, 'courses').stdout)['result']
            self.assertEqual([(c['name'], c['title'], c['sources'], c['concepts']) for c in listed['courses']], [('quantum-v1', 'Quantum', 0, 0)])

    def test_setup_installs_the_bundled_skill_and_keeps_foreign_folders(self):
        with tempfile.TemporaryDirectory() as home:
            old = Path(home) / '.skills' / 'guided-learning'
            old.mkdir(parents=True)
            (old / 'SKILL.md').write_text('---\nname: guided-learning\n---\n', encoding='utf-8')
            result = cli(home, 'setup', '--no-open')
            self.assertFalse(old.exists(), 'the skill under its old name is removed')
            self.assertEqual(result.returncode, 0, result.stderr)
            skill = Path(home) / '.skills' / 'throughline'
            self.assertIn('name: throughline', (skill / 'SKILL.md').read_text(encoding='utf-8'))
            self.assertTrue((skill / 'references' / 'course-operations.md').is_file())
            self.assertTrue((skill / 'agents' / 'openai.yaml').is_file())
            self.assertEqual(cli(home, 'setup', '--no-open').returncode, 0, 'setup is repeatable for updates')
            for child in skill.rglob('*'):
                if child.is_file():
                    child.unlink()
            (skill / 'SKILL.md').write_text('---\nname: something-else\n---\n', encoding='utf-8')
            self.assertEqual(cli(home, 'setup', '--no-open').returncode, 1)
            self.assertIn('something-else', (skill / 'SKILL.md').read_text(encoding='utf-8'))

    def test_setup_prepares_the_library_launcher_and_welcome_guide(self):
        with tempfile.TemporaryDirectory() as home:
            result = cli(home, 'setup', '--no-open')
            self.assertEqual(result.returncode, 0, result.stderr)
            agents = Path(home) / 'AGENTS.md'
            self.assertIn('$throughline', agents.read_text(encoding='utf-8'))
            self.assertIn('## Throughline ', result.stdout)
            self.assertIn(f'Your Throughline folder: `{Path(home)}`', result.stdout)
            self.assertIn('New course', result.stdout)
            self.assertNotIn('growing intervals', result.stdout, 'review has no schedule (ADR 0014)')
            self.assertNotIn('codex://', result.stdout)
            self.assertNotIn('Throughline is open at', result.stdout, '--no-open leaves the app closed')
            # As on Windows, where output piped to Codex is in a code page that has no Chinese.
            chinese = cli(home, 'setup', '--no-open', '--no-launcher', '--language', 'zh-CN', PYTHONIOENCODING='cp1252')
            self.assertEqual(chinese.returncode, 0, chinese.stderr)
            self.assertIn('已安装', chinese.stdout)
            self.assertIn('When the learner has not said what to do', agents.read_text(encoding='utf-8'))
            if os.name == 'nt':
                launcher = Path(home) / '.appdata' / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Throughline.lnk'
                self.assertTrue(launcher.is_file())
            elif sys.platform != 'darwin':
                launcher = Path(home) / '.xdg' / 'applications' / 'throughline.desktop'
                self.assertIn('-m guided_learning open', launcher.read_text(encoding='utf-8'))
                icon = next(l for l in launcher.read_text(encoding='utf-8').splitlines() if l.startswith('Icon='))[5:]
                self.assertTrue(Path(icon).is_file(), icon)
            self.assertEqual(json.loads(cli(home, 'courses').stdout)['result']['courses'], [], 'library files are not courses')
            agents.write_text('# My own notes\n', encoding='utf-8')
            again = cli(home, 'setup', '--no-open', '--no-launcher')
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(agents.read_text(encoding='utf-8'), '# My own notes\n')
            self.assertIn('Kept your own', again.stdout)

    def test_codex_changes_reach_open_tabs(self):
        with tempfile.TemporaryDirectory() as root, watched(root) as (app, events, polls):
            course(Path(root) / 'beta', 'Beta')
            polls()
            self.assertIn({'type': 'changed', 'scope': 'library'}, events)
            self.assertNotIn({'type': 'changed', 'scope': 'state'}, events, 'another course changing leaves the open one alone')
            execute(Path(root) / 'alpha', {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}, {'id': 'more', 'title': 'More'}], 'route': ['state', 'more'], 'coverage': []})
            polls()
            self.assertIn({'type': 'changed', 'scope': 'state'}, events)
        # Closing waits for a poll in progress, which reads the courses' databases; Windows cannot remove a course
        # folder while its database is open (#196).
        self.assertFalse(app.state.courses.watcher.is_alive())

    def test_the_hosts_own_writes_do_not_reload_its_tabs(self):
        with tempfile.TemporaryDirectory() as root, watched(root) as (app, events, polls):
            route = {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}, {'id': 'more', 'title': 'More'}], 'route': ['state', 'more'], 'coverage': []}
            app.state.courses.host.operation(route)
            polls()
            self.assertIn({'type': 'changed', 'scope': 'library'}, events)
            self.assertNotIn({'type': 'changed', 'scope': 'state'}, events, 'the host announces its own changes')
            execute(Path(root) / 'alpha', {**route, 'concepts': route['concepts'] + [{'id': 'last', 'title': 'Last'}], 'route': ['state', 'more', 'last']})
            polls()
            self.assertIn({'type': 'changed', 'scope': 'state'}, events)

    def test_codexs_write_during_one_of_the_hosts_is_still_its_own_change(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'alpha'
            course(path, 'Alpha')
            host = Host(path, runner=Idle())
            try:
                real = host_module.execute

                def writing(workspace, request, **options):
                    result = real(workspace, request, **options)
                    if request['op'] == 'memory.save' and request['id'] == 'pref':  # Codex commits as the host does
                        execute(path, {'op': 'memory.save', 'id': 'other', 'kind': 'preference', 'concept_id': 'state', 'text': 'Examples first'})
                    return result
                host.operation({'op': 'memory.save', 'id': 'mine', 'kind': 'preference', 'concept_id': 'state', 'text': 'Short answers'})
                self.assertFalse(host.outside_change(), "the host's own write")
                with mock.patch.object(host_module, 'execute', writing):
                    host.operation({'op': 'memory.save', 'id': 'pref', 'kind': 'preference', 'concept_id': 'state', 'text': 'Diagrams'})
                self.assertTrue(host.outside_change(), "Codex's write, though the host wrote at the same moment")
                self.assertFalse(host.outside_change(), 'told once')
            finally:
                host.close()

    def test_codex_changes_beyond_the_route_reach_open_tabs(self):
        # Studio adds exercises and notes memory through the skill, outside the host; the open course shows them at once.
        with tempfile.TemporaryDirectory() as root, watched(root) as (app, events, polls):
            for op in ('course.status', 'practice.list', 'memory.view', 'review.context'):
                execute(Path(root) / 'alpha', {'op': op})
            polls()
            self.assertNotIn({'type': 'changed', 'scope': 'state'}, events, 'reading the course changes nothing')
            execute(Path(root) / 'alpha', {'op': 'practice.add', 'id': 'ps1', 'concept_id': 'state',
                                           'exercises': [{'question': 'Normalise a state.', 'origin': 'self_created'}]})
            polls()
            self.assertIn({'type': 'changed', 'scope': 'state'}, events)
            self.assertNotIn({'type': 'changed', 'scope': 'library'}, events, 'the library shows nothing exercises change')
            events.clear()
            execute(Path(root) / 'alpha', {'op': 'memory.note', 'turn_id': 't', 'concept_id': 'state', 'interaction_ids': [],
                                           'note': {'entries': [{'kind': 'taught_term', 'text': 'ket'}]}})
            polls()
            self.assertIn({'type': 'changed', 'scope': 'state'}, events)

    def test_a_course_summary_is_read_again_only_after_the_course_changes(self):
        from guided_learning import library
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'alpha'
            course(path, 'Alpha')
            written_ago(path, 10)
            self.assertEqual(library.summary(path)['concepts'], 1)
            with mock.patch.object(library, '_summary', side_effect=AssertionError('read again')):
                self.assertEqual(library.summary(path)['title'], 'Alpha')
            execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}, {'id': 'more', 'title': 'More'}], 'route': ['state', 'more'], 'coverage': []})
            self.assertEqual(library.summary(path)['concepts'], 2)

    def test_a_commit_that_leaves_the_files_stamp_as_it_was_is_still_seen(self):
        # Within one tick of the file system's clock, and once the write-ahead log has wrapped, a commit can leave the
        # database files' modification times and sizes as they were; a course written that recently is read again.
        from guided_learning import library
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'alpha'
            course(path, 'Alpha')
            files = [f for f in (path / 'course.sqlite3', path / 'course.sqlite3-wal') if f.exists()]
            before = [(f.stat().st_mtime_ns, f.stat().st_size) for f in files]
            self.assertEqual(library.summary(path)['concepts'], 1)
            execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'S'}, {'id': 'b', 'title': 'B'}], 'route': ['state', 'b'], 'coverage': []})
            for f, (mtime, _) in zip(files, before):
                os.utime(f, ns=(mtime, mtime))
            self.assertEqual([(f.stat().st_mtime_ns, f.stat().st_size) for f in files], before, 'the same stamp')
            self.assertEqual(library.summary(path)['concepts'], 2)

    def test_one_broken_course_is_listed_with_its_error_beside_the_others(self):
        from guided_learning import library, migrations
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as config:
            course(Path(root) / 'alpha', 'Alpha')
            course(Path(root) / 'beta', 'Beta')
            (Path(root) / 'corrupt').mkdir()
            (Path(root) / 'corrupt' / 'course.sqlite3').write_bytes(b'not a database' * 100)
            # Beta is an older format whose migration fails.
            old = sqlite3.connect(Path(root) / 'beta' / 'course.sqlite3')
            old.execute("UPDATE documents SET value=? WHERE namespace='course' AND key='schema'", (json.dumps({'version': 6}),))
            old.commit()
            old.close()
            failing = [*migrations.MIGRATIONS[:-1], mock.Mock(side_effect=KeyError('chapters'))]
            app = create_app(port=8765, runner=Idle(), settings=TeacherSettings(Path(config) / 's.json'), library_root=root)
            with TestClient(app, base_url='http://127.0.0.1:8765') as client, mock.patch.object(migrations, 'MIGRATIONS', failing), \
                    self.assertLogs('guided_learning.library', 'ERROR') as logged:
                response = client.get('/api/library')
                self.assertEqual(response.status_code, 200)
                listed = {c['name']: c for c in response.json()['courses']}
                # Nothing keeps the broken file open, so the learner can replace it while Throughline runs (Windows).
                (Path(root) / 'corrupt' / 'course.sqlite3').unlink()
            self.assertEqual(listed['alpha']['title'], 'Alpha')
            self.assertIn('DatabaseError', listed['corrupt']['error'])
            self.assertIn("KeyError: 'chapters'", listed['beta']['error'])
            self.assertEqual(len(logged.records), 2)
            self.assertTrue(all(record.exc_info for record in logged.records), 'logged with the traceback')
            self.assertEqual(library.summary(Path(root) / 'beta')['title'], 'Beta', 'the course reads once its migration works')

    def test_the_watcher_reads_only_courses_whose_files_changed(self):
        from guided_learning import library
        with tempfile.TemporaryDirectory() as root, watched(root, also=['beta']) as (app, events, polls):
            read = []
            real = library.fingerprint
            with mock.patch.object(library, 'fingerprint', side_effect=lambda p: read.append(Path(p).name) or real(p)):
                polls()
                self.assertEqual(read, [], 'idle courses are not read')
                execute(Path(root) / 'beta', {'op': 'preferences.save', 'language': 'zh-CN'})
                polls()
                self.assertEqual(set(read), {'beta'})

    def test_host_switches_between_library_courses(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as config:
            course(Path(root) / 'alpha', 'Alpha')
            course(Path(root) / 'beta', 'Beta')
            (Path(root) / 'notes').mkdir()
            app = create_app(port=8765, runner=Idle(), settings=TeacherSettings(Path(config) / 's.json'), library_root=root)
            with TestClient(app, base_url='http://127.0.0.1:8765') as client:
                empty = client.get('/api/state')
                self.assertEqual((empty.status_code, empty.json()['code']), (409, 'no_course'))
                self.assertEqual(client.get('/api/settings').status_code, 200, 'settings work before a course is open')
                listed = client.get('/api/library').json()
                self.assertEqual(sorted(c['name'] for c in listed['courses']), ['alpha', 'beta'])
                self.assertIsNone(listed['active'])
                self.assertEqual(client.post('/api/library/open', json={'name': 'alpha'}).json()['active'], str((Path(root) / 'alpha').resolve()))
                self.assertEqual(client.get('/api/state').json()['course']['title'], 'Alpha')
                client.post('/api/library/open', json={'name': 'beta'})
                self.assertEqual(client.get('/api/state').json()['course']['title'], 'Beta')
                execute(Path(root) / 'alpha', {'op': 'course.status'})
                for name in ('../alpha', 'notes'):
                    self.assertGreaterEqual(client.post('/api/library/open', json={'name': name}).status_code, 400)
                self.assertEqual(client.get('/api/state').json()['course']['title'], 'Beta')

    def test_switching_releases_the_previous_course_lease(self):
        from guided_learning.server import Host
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as config:
            course(Path(root) / 'alpha', 'Alpha')
            course(Path(root) / 'beta', 'Beta')
            settings = TeacherSettings(Path(config) / 's.json')
            app = create_app(Path(root) / 'alpha', runner=Idle(), settings=settings, library_root=root)
            with TestClient(app, base_url='http://127.0.0.1:8765') as client:
                self.assertEqual(client.post('/api/library/open', json={'name': 'beta'}).status_code, 200)
                other = Host(Path(root) / 'alpha', runner=Idle(), settings=settings)
                other.close()

    def test_open_starts_one_background_host_and_stop_ends_it(self):
        with tempfile.TemporaryDirectory() as home:
            course(Path(home) / 'alpha', 'Alpha')
            first = cli(home, 'open', 'alpha', '--port', '0', '--no-browser')
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            record = json.loads((Path(home) / '.throughline' / 'host.json').read_text(encoding='utf-8'))
            try:
                again = cli(home, 'open', '--port', '0', '--no-browser')
                self.assertIn(f"127.0.0.1:{record['port']}", again.stdout, 'a running host is reused')
                self.assertEqual(json.loads((Path(home) / '.throughline' / 'host.json').read_text(encoding='utf-8'))['pid'], record['pid'])
                # The browser is signed in with a one-time code; the key itself is in no address or log.
                self.assertIn('/?code=', again.stdout)
                key = (Path(home) / '.throughline' / 'host.key').read_text(encoding='ascii')
                output = Path(home) / '.throughline' / 'host-output.log'
                self.assertNotIn(key, first.stdout + again.stdout + output.read_text(encoding='utf-8', errors='replace'))
                if os.name != 'nt':
                    self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                with mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': home}):
                    from guided_learning.commands import _call
                    self.assertTrue(_call(record['port'], 'GET', '/api/library')['active'].endswith('alpha'))
                self.assertEqual(cli(home, 'stop').returncode, 0)
            finally:
                for _ in range(100):
                    if not (Path(home) / '.throughline' / 'host.json').exists():
                        try:
                            # Windows can retain the child's log handles briefly after record cleanup.
                            for name in ('host-output.log', 'host.log'):
                                (Path(home) / '.throughline' / name).unlink(missing_ok=True)
                            break
                        except PermissionError:
                            pass
                    time.sleep(0.1)
                else:
                    os.kill(record['pid'], 9)
            self.assertFalse((Path(home) / '.throughline' / 'host.json').exists(), 'the host forgets its record when it stops')


if __name__ == '__main__':
    unittest.main()


class Migration(unittest.TestCase):
    def test_setup_moves_courses_from_the_old_documents_library(self):
        with tempfile.TemporaryDirectory() as home:
            old = Path(home) / 'Documents' / 'Throughline'
            course(old / 'alpha', 'Alpha')
            (old / 'AGENTS.md').write_text('<!-- Written by guided-learning setup; rerunning setup replaces this file. -->', encoding='utf-8')
            env = {**os.environ, 'HOME': home, 'USERPROFILE': home, 'XDG_DATA_HOME': str(Path(home) / '.xdg'),
                   'GUIDED_LEARNING_SKILLS_DIR': str(Path(home) / '.skills')}
            env.pop('GUIDED_LEARNING_HOME', None)
            result = subprocess.run([sys.executable, '-m', 'guided_learning', 'setup', '--no-open', '--no-launcher'], text=True, capture_output=True,
                                    cwd=ROOT, env=env, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Moved 1 course(s)', result.stdout)
            self.assertTrue((Path(home) / 'Throughline' / 'alpha' / 'course.sqlite3').is_file())
            self.assertFalse(old.exists(), 'the emptied old library is removed')


class LookingAfterCourses(unittest.TestCase):
    """Renaming, archiving, deleting to the trash and restoring library courses (ADR 0022)."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.config = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.root, ignore_errors=True))
        self.addCleanup(lambda: __import__('shutil').rmtree(self.config, ignore_errors=True))
        course(self.root / 'alpha', 'Alpha')
        course(self.root / 'beta', 'Beta')
        execute(self.root / 'alpha', {'op': 'memory.save', 'id': 'pref-1', 'kind': 'preference', 'text': 'Worked examples first'})
        self.app = create_app(port=8765, runner=Idle(), settings=TeacherSettings(self.config / 's.json'), library_root=self.root)
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.courses = self.app.state.courses

    def listed(self):
        return {c['name']: c for c in self.client.get('/api/library').json()['courses']}

    def test_renaming_changes_the_title_and_keeps_the_id_and_folder(self):
        before = execute(self.root / 'alpha', {'op': 'course.status'})['course']
        renamed = self.client.put('/api/library/courses/alpha/title', json={'title': '  Quantum, again '})
        self.assertEqual(renamed.json(), {'name': 'alpha', 'title': 'Quantum, again'})
        self.assertEqual(self.listed()['alpha']['title'], 'Quantum, again')
        after = execute(self.root / 'alpha', {'op': 'course.status'})['course']
        self.assertEqual(after['id'], before['id'], 'drafts and Studio chats refer to the id and folder')
        self.assertTrue((self.root / 'alpha' / 'course.sqlite3').is_file())
        self.assertEqual(self.client.put('/api/library/courses/alpha/title', json={'title': '  '}).status_code, 409)
        self.assertEqual(self.client.put('/api/library/courses/gamma/title', json={'title': 'X'}).status_code, 404)
        self.assertGreaterEqual(self.client.put('/api/library/courses/..%2Falpha/title', json={'title': 'X'}).status_code, 400)

    def test_renaming_the_open_course_goes_through_its_host(self):
        self.client.post('/api/library/open', json={'name': 'alpha'})
        self.client.put('/api/library/courses/alpha/title', json={'title': 'Renamed'})
        self.assertEqual(self.client.get('/api/state').json()['course']['title'], 'Renamed')

    def test_archiving_hides_nothing_but_marks_the_course_and_never_writes_to_it(self):
        database = self.root / 'alpha' / 'course.sqlite3'
        stamp = library_stamp(self.root / 'alpha')
        self.assertEqual(self.client.put('/api/library/courses/alpha/archived', json={'archived': True}).json(), {'name': 'alpha', 'archived': True})
        listed = self.listed()
        self.assertTrue(listed['alpha']['archived'])
        self.assertFalse(listed['beta']['archived'])
        self.assertEqual(library_stamp(self.root / 'alpha'), stamp, 'archiving changes nothing in the course')
        self.assertTrue(database.is_file())
        self.client.put('/api/library/courses/alpha/archived', json={'archived': False})
        self.assertFalse(self.listed()['alpha']['archived'])
        self.assertEqual(self.client.put('/api/library/courses/gamma/archived', json={'archived': True}).status_code, 404)

    def test_a_deleted_course_leaves_the_listing_and_comes_back_whole(self):
        self.client.put('/api/library/courses/alpha/archived', json={'archived': True})
        deleted = self.client.delete('/api/library/courses/alpha')
        self.assertEqual(deleted.status_code, 200, deleted.text)
        entry = deleted.json()
        self.assertEqual((entry['name'], entry['title']), ('alpha', 'Alpha'))
        self.assertEqual(set(self.listed()), {'beta'})
        self.assertFalse((self.root / 'alpha').exists())
        waiting = self.root / '.throughline' / 'trash' / entry['id'] / 'alpha' / 'course.sqlite3'
        self.assertTrue(waiting.is_file(), 'the course is moved, never removed')
        view = self.client.get('/api/library').json()
        self.assertEqual([(e['id'], e['name'], e['title']) for e in view['trash']], [(entry['id'], 'alpha', 'Alpha')])
        self.assertEqual(view['trash_folder'], str(self.root / '.throughline' / 'trash'))
        self.assertEqual(self.client.post('/api/library/open', json={'name': 'alpha'}).status_code, 404)

        restored = self.client.post(f"/api/library/trash/{entry['id']}/restore")
        self.assertEqual(restored.json(), {'name': 'alpha', 'title': 'Alpha'})
        self.assertEqual(set(self.listed()), {'alpha', 'beta'})
        self.assertFalse(self.listed()['alpha']['archived'], 'a restored course comes back to the main list')
        self.assertEqual(self.client.get('/api/library').json()['trash'], [])
        memory = execute(self.root / 'alpha', {'op': 'memory.view'})
        self.assertIn('Worked examples first', json.dumps(memory), 'learning records come back with the course')
        self.assertEqual(self.client.post(f"/api/library/trash/{entry['id']}/restore").status_code, 404)
        self.assertEqual(self.client.post('/api/library/trash/..%2F..%2Fbeta/restore').status_code, 404)

    def test_a_course_restored_after_its_name_was_taken_gets_a_free_one(self):
        entry = self.client.delete('/api/library/courses/alpha').json()
        course(self.root / 'alpha', 'Another alpha')
        restored = self.client.post(f"/api/library/trash/{entry['id']}/restore").json()
        self.assertEqual(restored, {'name': 'alpha-2', 'title': 'Alpha'})
        self.assertEqual({n: c['title'] for n, c in self.listed().items()}, {'alpha': 'Another alpha', 'alpha-2': 'Alpha', 'beta': 'Beta'})

    def test_a_write_running_when_a_course_is_deleted_finishes_first(self):
        writer = sqlite3.connect(self.root / 'alpha' / 'course.sqlite3')
        writer.execute('BEGIN IMMEDIATE')  # a command-line write halfway through
        deleting = threading.Thread(target=library.trash, args=(self.root, 'alpha'))
        deleting.start()
        deleting.join(0.5)
        self.assertTrue((self.root / 'alpha' / 'course.sqlite3').is_file(), 'the course waits for the write')
        writer.rollback()
        writer.close()
        deleting.join(10)
        self.assertFalse((self.root / 'alpha').exists())

    def test_a_write_that_opened_a_course_before_it_was_deleted_is_refused(self):
        source = self.root / 'notes.md'
        source.write_text('# Notes\nA state is a ray.', encoding='utf-8')
        stale = Store(self.root / 'alpha')  # Codex's command opened the course, then the learner deleted it
        if os.name == 'nt':
            # Windows refuses to move a folder with an open file, so the course stays, and takes writes once it closes.
            with self.assertRaises(OperationError) as refused:
                library.trash(self.root, 'alpha')
            stale.db.close()
            self.assertEqual(refused.exception.code, 'course_in_use')
            self.assertFalse((self.root / 'alpha' / api.MOVING).exists())
            execute(self.root / 'alpha', {'op': 'source.register', 'path': str(source)})
            return
        deleted = library.trash(self.root, 'alpha')
        try:
            with self.assertRaises(OperationError) as refused:
                api._write(stale, sources.register, {'op': 'source.register', 'path': str(source)})
        finally:
            stale.db.close()
        self.assertEqual(refused.exception.code, 'course_moved')
        self.assertFalse((self.root / 'alpha').exists(), 'nothing was written where the course used to be')
        library.restore(self.root, deleted['id'])
        self.assertFalse((self.root / 'alpha' / api.MOVING).exists())
        execute(self.root / 'alpha', {'op': 'source.register', 'path': str(source)})  # a restored course takes writes again

    def test_the_trash_is_left_out_of_the_command_listing_and_imports(self):
        self.client.delete('/api/library/courses/alpha')
        from guided_learning import library, packages
        self.assertEqual([c['name'] for c in library.list_courses(self.root)], ['beta'])
        self.assertEqual(packages.suggested_name(self.root, 'alpha'), 'alpha', 'a deleted course does not take its name')

    def test_studio_chats_follow_the_course_to_the_trash_and_back(self):
        studio = self.courses.studio
        studio._record(self.root / 'alpha', 'thread-1')
        entry = self.client.delete('/api/library/courses/alpha').json()
        self.assertEqual(studio._ids(self.root / 'alpha'), [], 'a new course named alpha does not list them')
        self.client.post(f"/api/library/trash/{entry['id']}/restore")
        self.assertEqual(studio._ids(self.root / 'alpha'), ['thread-1'])

    def test_deleting_the_open_course_closes_it_when_nothing_is_being_written(self):
        self.client.post('/api/library/open', json={'name': 'alpha'})
        self.assertEqual(self.client.delete('/api/library/courses/alpha').status_code, 200)
        self.assertEqual(self.client.get('/api/state').json()['code'], 'no_course')
        self.assertIsNone(self.client.get('/api/library').json()['active'])

    def test_deleting_waits_for_a_lesson_being_written(self):
        self.client.post('/api/library/open', json={'name': 'alpha'})
        host = self.courses.host
        with host._streams:
            host._live[('turn', 1)] = 'mainline'
        refused = self.client.delete('/api/library/courses/alpha')
        self.assertEqual((refused.status_code, refused.json()['code']), (409, 'course_busy'))
        self.assertTrue((self.root / 'alpha' / 'course.sqlite3').is_file())
        with host._streams:
            host._live[('turn', 1)] = 'preparation'
        self.assertFalse(host.writing(), 'background work does not hold a course')
        with host._streams:
            host._live.clear()

    def test_deleting_waits_for_studio(self):
        with mock.patch.object(self.courses.studio, 'activity', return_value={'running': ['thread-1'], 'waiting': []}):
            refused = self.client.delete('/api/library/courses/beta')
        self.assertEqual((refused.status_code, refused.json()['code']), (409, 'course_busy'))
        self.assertIn('beta', self.listed())

    def test_deleting_is_refused_while_another_host_holds_the_course(self):
        other = Host(self.root / 'beta', runner=Idle(), settings=TeacherSettings(self.config / 'other.json'))
        try:
            refused = self.client.delete('/api/library/courses/beta')
            self.assertEqual((refused.status_code, refused.json()['code']), (409, 'host_running'))
            self.assertIn('beta', self.listed())
            self.assertFalse(any((self.root / '.throughline' / 'trash').glob('*/')), 'nothing is left half moved')
        finally:
            other.close()


def library_stamp(path):
    from guided_learning import library
    return library.stamp(path), (Path(path) / 'course.sqlite3').read_bytes()
