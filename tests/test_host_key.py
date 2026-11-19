"""The host key: only a browser or command that shows it can use the host's API (other people's programs on a shared
computer can reach loopback too)."""
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from guided_learning import commands, library, web
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings

KEY = 'a' * 64


class Signed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        app = create_app(port=8765, settings=TeacherSettings(root / 'settings.json'), library_root=root / 'library', key=KEY)
        self.client = TestClient(app, base_url='http://127.0.0.1:8765', follow_redirects=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_the_api_refuses_a_browser_that_is_not_signed_in(self):
        response = self.client.get('/api/library')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'not_signed_in')
        self.assertIn('launcher', response.json()['error'])
        self.assertEqual(self.client.put('/api/studio/access', json={'full_access': True}).status_code, 401)

    def code(self):
        return self.client.post('/api/sign-in', json={}, headers={'X-Throughline-Key': KEY}).json()['code']

    def test_a_one_time_code_signs_the_browser_in_without_the_key(self):
        code = self.code()
        self.assertNotIn(KEY, code)
        response = self.client.get(f'/?code={code}')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], '/')  # the code leaves the address bar
        cookie = response.headers['set-cookie']
        self.assertIn('throughline-8765=', cookie)
        self.assertNotIn(KEY, cookie)  # the browser holds a token derived from the key, never the key
        self.assertIn('HttpOnly', cookie)
        self.assertIn('samesite=strict', cookie.lower())
        self.assertEqual(self.client.get('/api/library').status_code, 200)

    def test_a_code_signs_in_once(self):
        code = self.code()
        self.client.get(f'/?code={code}')
        self.client.cookies.clear()
        response = self.client.get(f'/?code={code}')
        self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(self.client.get('/api/library').status_code, 401)

    def test_neither_the_key_nor_a_made_up_code_signs_a_browser_in(self):
        for address in (f'/?code={KEY}', '/?code=' + 'b' * 32, f'/?key={KEY}'):
            response = self.client.get(address)
            self.assertNotIn('set-cookie', response.headers, address)
        self.assertEqual(self.client.get('/api/library').status_code, 401)

    def test_an_expired_code_signs_nothing_in(self):
        code = self.code()
        with mock.patch('guided_learning.server.app.time.monotonic', return_value=time.monotonic() + 301):
            response = self.client.get(f'/?code={code}')
        self.assertNotIn('set-cookie', response.headers)

    def test_only_a_command_with_the_key_gets_a_code(self):
        self.assertEqual(self.client.post('/api/sign-in', json={}).status_code, 401)

    def test_a_cookie_for_another_port_does_not_count(self):
        self.client.get(f'/?code={self.code()}')
        token = self.client.cookies.get('throughline-8765')
        self.client.cookies.clear()
        self.client.cookies.set('throughline-9999', token)
        self.assertEqual(self.client.get('/api/library').status_code, 401)
        self.client.cookies.set('throughline-8765', KEY)  # the key is not the browser's token
        self.assertEqual(self.client.get('/api/library').status_code, 401)

    def test_a_command_sends_the_key_in_a_header(self):
        self.assertEqual(self.client.get('/api/library', headers={'X-Throughline-Key': KEY}).status_code, 200)
        self.assertEqual(self.client.get('/api/library', headers={'X-Throughline-Key': 'nope'}).status_code, 401)

    def test_the_liveness_probe_needs_no_key(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)


class Unsigned(unittest.TestCase):
    def test_without_a_key_the_host_answers_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(port=8765, settings=TeacherSettings(root / 'settings.json'), library_root=root / 'library')
            with TestClient(app, base_url='http://127.0.0.1:8765') as client:
                self.assertEqual(client.get('/api/library').status_code, 200)


class Key(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_key_is_kept_across_launches_and_only_this_user_reads_it(self):
        key = library.host_key()
        self.assertRegex(key, r'^[0-9a-f]{64}$')
        self.assertEqual(library.host_key(), key)
        path = library.state_dir() / 'host.key'
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(list(path.parent.glob('*.partial')), [])

    def test_the_key_earlier_versions_printed_is_replaced(self):
        old = library.state_dir() / 'host-key'
        old.parent.mkdir(parents=True)
        old.write_text('c' * 64, encoding='ascii')
        self.assertNotEqual(library.host_key(), 'c' * 64)
        self.assertEqual(library.legacy_host_key(), 'c' * 64, 'kept to stop a host of theirs still running')
        library.forget_legacy_host_key()
        self.assertFalse(old.exists())
        self.assertIsNone(library.legacy_host_key())

    def test_a_damaged_key_is_replaced(self):
        path = library.state_dir() / 'host.key'
        path.parent.mkdir(parents=True)
        path.write_text('not a key', encoding='ascii')
        self.assertRegex(library.host_key(), r'^[0-9a-f]{64}$')

    def test_the_launcher_opens_an_address_with_a_code_from_the_host(self):
        with mock.patch.object(commands, '_call', return_value={'code': 'f' * 32}) as call:
            self.assertEqual(commands.app_url(8765), 'http://127.0.0.1:8765/?code=' + 'f' * 32)
        call.assert_called_once_with(8765, 'POST', '/api/sign-in', {})
        with mock.patch.object(commands, '_call', side_effect=OSError('refused')):
            self.assertEqual(commands.app_url(8765), 'http://127.0.0.1:8765/')

    def run_host(self, *flags):
        printed = []
        def serve(*args, on_ready, sign_in, **kwargs):
            on_ready(8765)
            printed.append(sign_in)
        with mock.patch.object(web, 'serve', serve), mock.patch.object(web, '_record'), mock.patch.object(web, '_forget'), \
                mock.patch.object(sys, 'argv', ['guided-learning-web', '--port', '0', *flags]), \
                mock.patch('builtins.print') as output:
            web.main()
        return printed[0], ' '.join(str(c.args) for c in output.call_args_list)

    def test_the_host_is_started_with_the_key_and_never_prints_it(self):
        sign_in, printed = self.run_host()
        self.assertEqual(sign_in.key, library.host_key())
        self.assertNotIn(library.host_key(), printed)
        self.assertIn('?code=', printed)  # someone running it in a terminal can open it

    def test_the_launchers_host_prints_no_secret_to_its_output_log(self):
        with mock.patch.object(web.logs, 'configure'):
            sign_in, printed = self.run_host('--record')
        self.assertNotIn(library.host_key(), printed)
        self.assertNotIn('code=', printed)


if __name__ == '__main__':
    unittest.main()
