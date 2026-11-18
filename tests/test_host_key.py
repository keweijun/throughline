"""The host key: only a browser or command that shows it can use the host's API (other people's programs on a shared
computer can reach loopback too)."""
import os
import stat
import sys
import tempfile
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

    def test_opening_the_address_with_the_key_signs_the_browser_in(self):
        response = self.client.get(f'/?key={KEY}')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], '/')  # the key leaves the address bar
        cookie = response.headers['set-cookie']
        self.assertIn('throughline-key-8765=', cookie)
        self.assertIn('HttpOnly', cookie)
        self.assertIn('samesite=strict', cookie.lower())
        self.assertEqual(self.client.get('/api/library').status_code, 200)

    def test_a_wrong_key_signs_nothing_in(self):
        response = self.client.get('/?key=' + 'b' * 64)
        self.assertEqual(response.status_code, 303)
        self.assertNotIn('set-cookie', response.headers)
        self.assertEqual(self.client.get('/api/library').status_code, 401)

    def test_a_cookie_for_another_port_does_not_count(self):
        self.client.cookies.set('throughline-key-9999', KEY)
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
        path = library.state_dir() / 'host-key'
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(list(path.parent.glob('*.partial')), [])

    def test_a_damaged_key_is_replaced(self):
        path = library.state_dir() / 'host-key'
        path.parent.mkdir(parents=True)
        path.write_text('not a key', encoding='ascii')
        self.assertRegex(library.host_key(), r'^[0-9a-f]{64}$')

    def test_the_launcher_opens_an_address_that_signs_in(self):
        self.assertEqual(commands.app_url(8765), f'http://127.0.0.1:8765/?key={library.host_key()}')

    def test_the_recorded_host_is_started_with_the_key(self):
        with mock.patch.object(web, 'serve') as serve, mock.patch.object(sys, 'argv', ['guided-learning-web', '--port', '0']):
            web.main()
        self.assertEqual(serve.call_args.kwargs['key'], library.host_key())


if __name__ == '__main__':
    unittest.main()
