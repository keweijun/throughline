import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from guided_learning import library, updates
from guided_learning.store import OperationError
from support import host_client


def course(path):
    from guided_learning.api import execute
    execute(path, {'op': 'course.init', 'title': 'Quantum'})


class UpdateCheck(unittest.TestCase):
    def test_versions_compare_by_number_and_a_checkout_is_never_behind(self):
        self.assertTrue(updates.newer('0.10.0', '0.9.3'))
        self.assertTrue(updates.newer('0.5.2', '0.5.1'))
        self.assertFalse(updates.newer('0.5.1', '0.5.1'))
        self.assertFalse(updates.newer('0.5.0', '0.5.1'))
        self.assertFalse(updates.newer('0.6.0', 'development'))

    def test_the_host_reports_main_s_declared_version(self):
        updates._found.clear()
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / 'pyproject.toml'
            remote.write_text('[project]\nname = "throughline"\nversion = "9.0.0"\n', encoding='utf-8')
            course(Path(tmp) / 'course')
            client, _ = host_client(Path(tmp) / 'course')
            with client, mock.patch.dict(os.environ, {'GUIDED_LEARNING_UPDATE_URL': remote.as_uri()}), \
                    mock.patch.object(updates, 'version', return_value='0.5.1'), \
                    mock.patch('guided_learning.server.app.version', return_value='0.5.1'):
                self.assertEqual(client.get('/api/about').json(), {'version': '0.5.1'})
                result = client.get('/api/update').json()
                self.assertEqual(result, {'version': '0.5.1', 'latest': '9.0.0', 'available': True})
                remote.write_text('version = "0.5.1"\n', encoding='utf-8')
                self.assertTrue(client.get('/api/update').json()['available'], 'a launch check reuses the version found')
                self.assertFalse(client.get('/api/update?fresh=1').json()['available'])
                remote.unlink()
                missing = client.get('/api/update?fresh=1')
                self.assertEqual(missing.status_code, 502)
                self.assertEqual(missing.json()['code'], 'update_check_failed')


def fake_codex(folder, script):
    """A `codex` that records its arguments, then runs `script` with the --output-last-message path as `result`."""
    path = Path(folder) / 'codex'
    path.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
json.dump(sys.argv[1:], open({str(Path(folder) / 'args.json')!r}, 'w'))
result = Path(sys.argv[sys.argv.index('--output-last-message') + 1])
{script}
''', encoding='utf-8')
    path.chmod(0o755)
    return str(path)


def settle(folder, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = updates.progress(folder)
        if not record or record['state'] != 'running':
            return record
        time.sleep(0.05)
    raise AssertionError('the update never settled')


AVAILABLE = {'version': '0.5.1', 'latest': '0.6.0', 'available': True}


@unittest.skipIf(os.name == 'nt', 'the fake codex is a script with a shebang')
class BackgroundUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / '.throughline'
        for patch in (mock.patch.object(updates, 'check', return_value=AVAILABLE),
                      mock.patch.object(updates, 'version', return_value='0.5.1')):
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self.reap)

    def reap(self):
        process = updates._process.pop('codex', None)
        if process:
            process.kill()
            process.wait()

    def test_codex_runs_unattended_with_the_readme_request_and_reopens_the_course_on_this_port(self):
        codex = fake_codex(self.tmp.name, 'result.write_text(json.dumps({"ok": False, "version": "0.5.1", "message": "uv could not reach GitHub."}))')
        record = updates.install(self.folder, 8770, 'quantum-v1', 'zh-CN', command=codex)
        self.assertEqual((record['state'], record['from'], record['to']), ('running', '0.5.1', '0.6.0'))
        failed = settle(self.folder)
        self.assertEqual((failed['state'], failed['message']), ('failed', 'uv could not reach GitHub.'))
        args = json.loads((Path(self.tmp.name) / 'args.json').read_text())
        self.assertEqual(args[0], 'exec')
        self.assertIn('--dangerously-bypass-approvals-and-sandbox', args)
        self.assertIn('--ephemeral', args)
        schema = json.loads(Path(args[args.index('--output-schema') + 1]).read_text())
        self.assertEqual(schema['required'], ['ok', 'version', 'message'])
        request = args[-1]
        self.assertTrue(request.startswith('Update https://github.com/keweijun/throughline'), 'the same request as the chat hand-off')
        self.assertIn('guided-learning setup --no-open', request)
        self.assertIn('guided-learning open quantum-v1 --no-browser --port 8770', request)
        self.assertIn('Simplified Chinese', request)
        self.assertEqual(updates.progress(self.folder)['state'], 'failed', 'a failure stays until the next attempt')

    def test_a_codex_that_exits_without_answering_fails_with_its_error(self):
        codex = fake_codex(self.tmp.name, 'print(json.dumps({"type": "error", "message": "Not signed in"})); sys.exit(1)')
        updates.install(self.folder, 8765, command=codex)
        failed = settle(self.folder)
        self.assertEqual(failed['message'], 'Codex stopped before installing the update: Not signed in')

    def test_one_update_at_a_time_and_the_new_version_clears_it(self):
        codex = fake_codex(self.tmp.name, 'import time; time.sleep(30)')
        updates.install(self.folder, 8765, command=codex)
        with self.assertRaises(OperationError) as raised:
            updates.install(self.folder, 8765, command=codex)
        self.assertEqual(raised.exception.code, 'update_running')
        # The next host is the new version: it has nothing to report and leaves no status behind.
        with mock.patch.object(updates, 'version', return_value='0.6.0'):
            self.assertIsNone(updates.progress(self.folder))
        self.assertFalse((self.folder / updates.STATUS).exists())

    def test_an_update_that_never_finishes_fails(self):
        self.folder.mkdir()
        (self.folder / updates.STATUS).write_text(json.dumps(
            {'state': 'running', 'from': '0.5.1', 'to': '0.6.0', 'started': time.time() - updates.GIVE_UP - 1, 'log': 'update.log'}))
        updates._process.clear()  # started by an earlier host
        self.assertIn('did not finish in 20 minutes', updates.progress(self.folder)['message'])

    def test_no_update_without_a_newer_version_or_without_codex(self):
        with mock.patch.object(updates, 'check', return_value={**AVAILABLE, 'latest': '0.5.1', 'available': False}), \
                self.assertRaises(OperationError) as raised:
            updates.install(self.folder, 8765, command='codex')
        self.assertEqual(raised.exception.code, 'update_not_available')
        with mock.patch.object(updates, 'find_codex', return_value=None), self.assertRaises(OperationError) as raised:
            updates.install(self.folder, 8765)
        self.assertEqual(raised.exception.code, 'codex_missing')
        self.assertFalse((self.folder / updates.STATUS).exists())

    def test_the_host_starts_the_update_for_its_open_course_and_reports_it(self):
        codex = fake_codex(self.tmp.name, 'result.write_text(json.dumps({"ok": False, "version": "0.5.1", "message": "No network."}))')
        library_root = Path(self.tmp.name) / 'library'
        course(library_root / 'quantum-v1')
        from fastapi.testclient import TestClient
        from guided_learning.server import create_app
        from guided_learning.server.settings import TeacherSettings
        app = create_app(library_root / 'quantum-v1', settings=TeacherSettings(Path(self.tmp.name) / 'settings.json'),
                         library_root=library_root)
        with TestClient(app, base_url='http://127.0.0.1:8765') as client, mock.patch.object(library, 'state_dir', return_value=self.folder), \
                mock.patch.object(updates, 'find_codex', return_value=codex):
            self.assertEqual(client.get('/api/update/install').json(), {'update': None})
            app.state.courses.studio.active['t1'] = 'turn-1'
            busy = client.post('/api/update/install', json={'language': 'en'})
            self.assertEqual((busy.status_code, busy.json()['code']), (409, 'studio_running'), 'a Studio turn would be cut off')
            app.state.courses.studio.active.clear()
            started = client.post('/api/update/install', json={'language': 'en'})
            self.assertEqual(started.status_code, 200, started.text)
            self.assertEqual(started.json()['update']['to'], '0.6.0')
            settle(self.folder)
            self.assertEqual(client.get('/api/update/install').json()['update']['message'], 'No network.')
        request = json.loads((Path(self.tmp.name) / 'args.json').read_text())[-1]
        self.assertIn('guided-learning open quantum-v1 --no-browser', request)


if __name__ == '__main__':
    unittest.main()
