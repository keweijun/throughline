import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from guided_learning.api import execute
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings
from support import ROOT


def course(path, title):
    execute(path, {'op': 'course.init', 'title': title})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})


def cli(home, *args, stdin=''):
    env = {**os.environ, 'GUIDED_LEARNING_HOME': str(home), 'GUIDED_LEARNING_SKILLS_DIR': str(Path(home) / 'skills')}
    return subprocess.run([sys.executable, '-m', 'guided_learning', *args], input=stdin, text=True, encoding='utf-8',
                          capture_output=True, cwd=ROOT, env=env, timeout=60)


class Idle:
    def run(self, prompt, cwd, emit, cancel):
        cancel.wait(3)


class CourseLibrary(unittest.TestCase):
    def test_courses_by_name_and_listing(self):
        with tempfile.TemporaryDirectory() as home:
            created = cli(home, '--course', 'quantum-v1', stdin=json.dumps({'op': 'course.init', 'title': 'Quantum'}))
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.assertTrue((Path(home) / 'courses' / 'quantum-v1' / 'course.sqlite3').is_file())
            rejected = cli(home, '--course', '../escape', stdin=json.dumps({'op': 'course.status'}))
            self.assertEqual(json.loads(rejected.stdout)['error']['code'], 'invalid_course_name')
            listed = json.loads(cli(home, 'courses').stdout)['result']
            self.assertEqual([(c['name'], c['title'], c['sources'], c['concepts']) for c in listed['courses']], [('quantum-v1', 'Quantum', 0, 0)])

    def test_setup_installs_the_bundled_skill_and_keeps_foreign_folders(self):
        with tempfile.TemporaryDirectory() as home:
            result = cli(home, 'setup')
            self.assertEqual(result.returncode, 0, result.stderr)
            skill = Path(home) / 'skills' / 'guided-learning'
            self.assertIn('name: guided-learning', (skill / 'SKILL.md').read_text(encoding='utf-8'))
            self.assertTrue((skill / 'references' / 'course-operations.md').is_file())
            self.assertTrue((skill / 'agents' / 'openai.yaml').is_file())
            self.assertEqual(cli(home, 'setup').returncode, 0, 'setup is repeatable for updates')
            for child in skill.rglob('*'):
                if child.is_file():
                    child.unlink()
            (skill / 'SKILL.md').write_text('---\nname: something-else\n---\n', encoding='utf-8')
            self.assertEqual(cli(home, 'setup').returncode, 1)
            self.assertIn('something-else', (skill / 'SKILL.md').read_text(encoding='utf-8'))

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
            course(Path(home) / 'courses' / 'alpha', 'Alpha')
            first = cli(home, 'open', 'alpha', '--port', '0', '--no-browser')
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            record = json.loads((Path(home) / 'host.json').read_text(encoding='utf-8'))
            try:
                again = cli(home, 'open', '--port', '0', '--no-browser')
                self.assertIn(f"127.0.0.1:{record['port']}", again.stdout, 'a running host is reused')
                self.assertEqual(json.loads((Path(home) / 'host.json').read_text(encoding='utf-8'))['pid'], record['pid'])
                with mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': home}):
                    from guided_learning.commands import _call
                    self.assertTrue(_call(record['port'], 'GET', '/api/library')['active'].endswith('alpha'))
                self.assertEqual(cli(home, 'stop').returncode, 0)
            finally:
                for _ in range(100):
                    if not (Path(home) / 'host.json').exists():
                        break
                    time.sleep(0.1)
                else:
                    os.kill(record['pid'], 9)
            self.assertFalse((Path(home) / 'host.json').exists(), 'the host forgets its record when it stops')


if __name__ == '__main__':
    unittest.main()
