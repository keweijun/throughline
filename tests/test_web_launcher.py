"""The library's launcher card and Codex checks, through the host API with a fake launcher and fake checks."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from guided_learning import checks as codex_checks
from guided_learning.launcher import Launcher
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings


class Idle:
    def run(self, prompt, cwd, emit, cancel):
        cancel.wait(3)


class LauncherCard(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.home = Path(scratch.name)
        self.started = []

    def client(self, platform='linux', name='throughline.desktop', make=True, status=None):
        folder = self.home / ('Applications' if platform == 'darwin' else 'applications')
        path = folder / name
        if make:
            folder.mkdir(parents=True, exist_ok=True)
            if platform == 'darwin':
                (path / 'Contents').mkdir(parents=True)
            else:
                path.write_text('[Desktop Entry]\n', encoding='utf-8')
        launcher = Launcher(path, platform=platform, desktop=self.home / 'Desktop', start=self.started.append, output=lambda c: '')
        app = create_app(port=8765, runner=Idle(), settings=TeacherSettings(self.home / 'config' / 'settings.json'),
                         library_root=self.home / 'library', launcher=launcher,
                         checks=status or codex_checks.CodexStatus(cheap=lambda: [], probe=lambda: None))
        client = TestClient(app, base_url='http://127.0.0.1:8765')
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return client, path

    def test_status_until_dismissed_and_after(self):
        client, path = self.client()
        self.assertEqual(client.get('/api/launcher').json(),
                         {'platform': 'linux', 'path': str(path), 'exists': True, 'dismissed': False})
        self.assertEqual(client.post('/api/seen', json={'id': 'launcher'}).json(), {'seen': ['launcher']})
        self.assertTrue(client.get('/api/launcher').json()['dismissed'])
        saved = json.loads((self.home / 'config' / 'seen.json').read_text(encoding='utf-8'))
        self.assertEqual(saved, {'seen': ['launcher']}, 'saved beside the settings, per user')
        self.assertEqual(client.post('/api/seen', json={'id': '../x'}).status_code, 400)

    def test_dismissal_survives_saving_settings(self):
        client, _ = self.client()
        client.post('/api/seen', json={'id': 'launcher'})
        self.assertEqual(client.put('/api/settings', json={'model': 'm', 'effort': 'high'}).status_code, 200)
        self.assertTrue(client.get('/api/launcher').json()['dismissed'])

    def test_add_to_desktop_copies_the_launcher(self):
        client, path = self.client()
        added = client.post('/api/launcher/desktop').json()
        target = self.home / 'Desktop' / 'throughline.desktop'
        self.assertEqual(added, {'path': str(target)})
        self.assertEqual(target.read_text(encoding='utf-8'), path.read_text(encoding='utf-8'))
        self.assertTrue(os.access(target, os.X_OK), 'desktops launch only executable desktop files')
        self.assertEqual(client.post('/api/launcher/desktop').status_code, 200, 'adding again replaces it')

    def test_on_macos_the_desktop_gets_a_link_to_the_app(self):
        client, path = self.client(platform='darwin', name='Throughline.app')
        self.assertEqual(client.get('/api/launcher').json()['platform'], 'darwin-home')
        client.post('/api/launcher/desktop')
        target = self.home / 'Desktop' / 'Throughline.app'
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.resolve(), path.resolve())
        self.assertEqual(client.post('/api/launcher/desktop').status_code, 200)
        target.unlink()
        target.mkdir()
        self.assertEqual(client.post('/api/launcher/desktop').json()['code'], 'desktop_taken', 'never replaces a real app')

    def test_show_launcher_opens_the_file_manager(self):
        client, path = self.client()
        self.assertEqual(client.post('/api/launcher/show').status_code, 200)
        self.assertEqual(self.started, [['xdg-open', str(path.parent)]])
        mac, app = self.client(platform='darwin', name='Throughline.app')
        mac.post('/api/launcher/show')
        self.assertEqual(self.started[-1], ['open', '-R', str(app)])

    def test_without_a_launcher_the_actions_say_how_to_add_one(self):
        client, _ = self.client(make=False)
        self.assertFalse(client.get('/api/launcher').json()['exists'])
        for action in ('desktop', 'show'):
            refused = client.post(f'/api/launcher/{action}')
            self.assertEqual((refused.status_code, refused.json()['code']), (409, 'launcher_missing'))
            self.assertIn('guided-learning setup', refused.json()['error'])
        self.assertEqual(self.started, [])

    def test_checks_never_wait_for_the_probe_and_run_it_once(self):
        found = codex_checks.result('codex', True, 'codex-cli 1 (/bin/codex)')
        release, probed = threading.Event(), []

        def probe():
            probed.append(1)
            release.wait(5)
            return codex_checks.result('answers', len(probed) > 1, '' if len(probed) > 1 else '401 Unauthorized', model='luna', seconds=1.0)
        client, _ = self.client(status=codex_checks.CodexStatus(cheap=lambda: [found], probe=probe))
        self.assertEqual(client.get('/api/checks').json(), {'checks': [found], 'checking': True}, 'answers while the probe runs')
        release.set()
        failed = wait_for(client, lambda view: not view['checking'])
        self.assertEqual([(c['id'], c['ok'], c['detail']) for c in failed['checks']], [('codex', True, found['detail']), ('answers', False, '401 Unauthorized')])
        self.assertEqual(client.get('/api/checks').json(), failed, 'a failure is kept')
        self.assertEqual(len(probed), 1, 'once per host, not on every library load')

        release.clear()
        again = client.post('/api/checks').json()
        self.assertEqual(again, {**failed, 'checking': True}, 'the last answer stays while checking again')
        release.set()
        passed = wait_for(client, lambda view: not view['checking'])
        self.assertEqual([c['ok'] for c in passed['checks']], [True, True])
        self.assertEqual(len(probed), 2)

    def test_without_codex_nothing_is_probed(self):
        probed = []
        missing = codex_checks.result('codex', False)
        client, _ = self.client(status=codex_checks.CodexStatus(cheap=lambda: [missing], probe=lambda: probed.append(1)))
        self.assertEqual(client.get('/api/checks').json(), {'checks': [missing], 'checking': False})
        self.assertEqual(client.post('/api/checks').json(), {'checks': [missing], 'checking': False})
        self.assertEqual(probed, [])


def wait_for(client, done):
    for _ in range(200):
        view = client.get('/api/checks').json()
        if done(view):
            return view
        threading.Event().wait(0.02)
    raise AssertionError(view)


if __name__ == '__main__':
    unittest.main()
