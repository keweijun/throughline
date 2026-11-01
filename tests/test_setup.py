"""Setup's last steps: opening the app, the welcome guide and where the launcher goes."""
import argparse
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from guided_learning import checks, commands


def setup_args(**options):
    return argparse.Namespace(**{'no_launcher': True, 'no_open': False, 'language': 'en', **options})


class SetupOpensTheApp(unittest.TestCase):
    def run_setup(self, home, **options):
        env = {'GUIDED_LEARNING_HOME': home, 'GUIDED_LEARNING_SKILLS_DIR': str(Path(home) / '.skills')}
        output = io.StringIO()
        with mock.patch.dict(os.environ, env), redirect_stdout(output):
            code = commands.setup(setup_args(**options))
        return code, output.getvalue()

    def test_setup_opens_the_library_and_says_so(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(commands, 'open_app', return_value=True) as opener:
            code, output = self.run_setup(home)
        self.assertEqual(code, 0)
        opener.assert_called_once_with()
        self.assertIn('Throughline is open in your browser', output)

    def test_no_open_skips_it(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(commands, 'open_app') as opener:
            code, output = self.run_setup(home, no_open=True)
        self.assertEqual(code, 0)
        opener.assert_not_called()
        self.assertNotIn('open in your browser', output)
        self.assertIn('Open Throughline now', output)

    def test_a_host_that_does_not_start_does_not_fail_setup(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(commands, 'running', return_value=None), \
                mock.patch.object(commands, '_spawn', return_value=None):
            code, output = self.run_setup(home)
        self.assertEqual(code, 0)
        self.assertIn('Throughline did not start', output)
        self.assertIn('Open Throughline now', output)

    def test_a_browser_error_does_not_fail_setup(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(commands, 'running', return_value={'port': 9}), \
                mock.patch.object(commands, 'platform', return_value='darwin'), \
                mock.patch.object(commands.webbrowser, 'open', side_effect=OSError('no browser')):
            code, output = self.run_setup(home)
        self.assertEqual(code, 0)
        self.assertIn('could not be opened', output)

    def test_without_a_display_no_console_browser_is_started(self):
        with mock.patch.object(commands, 'running', return_value={'port': 9}), \
                mock.patch.object(commands, 'platform', return_value='linux'), \
                mock.patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}), \
                mock.patch.object(commands.webbrowser, 'open') as browser, redirect_stdout(io.StringIO()):
            self.assertFalse(commands.open_app())
        browser.assert_not_called()


class Welcome(unittest.TestCase):
    def test_the_guide_is_short_and_current(self):
        for language in commands.LANGUAGES:
            text = commands.welcome(Path('/courses'), Path('/x/throughline.desktop'), language, opened=True)
            self.assertIn(commands.version(), text)
            self.assertIn('/courses', text)
            self.assertIn('New course', text)
            self.assertLess(len(text.splitlines()), 10)
            self.assertNotIn('间隔', text)
            self.assertNotIn('intervals', text)

    def test_the_launcher_hint_matches_where_the_mac_launcher_went(self):
        with tempfile.TemporaryDirectory() as shared, mock.patch.object(commands, 'APPLICATIONS', Path(shared)), \
                mock.patch.object(commands, 'platform', return_value='darwin'):
            self.assertIn('the Applications folder', commands.launcher_hint(Path(shared) / 'Throughline.app', 'en'))
            home = commands.launcher_hint(Path.home() / 'Applications' / 'Throughline.app', 'en')
            self.assertIn('Applications in your home folder', home)
        self.assertIn('throughline', commands.launcher_hint(None, 'en'), 'without a launcher, the command opens it')


class MacLauncher(unittest.TestCase):
    def install(self, shared, home, writable):
        with mock.patch.object(commands, 'APPLICATIONS', Path(shared)), \
                mock.patch.object(commands, 'platform', return_value='darwin'), \
                mock.patch.object(commands.Path, 'home', return_value=Path(home)), \
                mock.patch.object(commands.os, 'access', return_value=writable):
            return commands.install_launcher(), commands.launcher_path()

    def test_the_shared_applications_folder_when_writable(self):
        with tempfile.TemporaryDirectory() as shared, tempfile.TemporaryDirectory() as home:
            installed, found = self.install(shared, home, writable=True)
            self.assertEqual(installed, Path(shared) / 'Throughline.app')
            self.assertEqual(found, installed)
            self.assertTrue((installed / 'Contents' / 'MacOS' / 'Throughline').is_file())
            self.assertIn(commands.BUNDLE_ID, (installed / 'Contents' / 'Info.plist').read_text(encoding='utf-8'))

    def test_applications_in_the_home_folder_otherwise(self):
        with tempfile.TemporaryDirectory() as shared, tempfile.TemporaryDirectory() as home:
            installed, found = self.install(shared, home, writable=False)
            self.assertEqual(installed, Path(home) / 'Applications' / 'Throughline.app')
            self.assertEqual(found, installed)
            self.assertFalse((Path(shared) / 'Throughline.app').exists())

    def test_moving_to_the_shared_folder_removes_the_old_launcher_but_not_a_stranger(self):
        with tempfile.TemporaryDirectory() as shared, tempfile.TemporaryDirectory() as home:
            old, _ = self.install(shared, home, writable=False)
            installed, _ = self.install(shared, home, writable=True)
            self.assertFalse(old.exists(), 'one launcher, so Spotlight finds one Throughline')
            self.assertTrue(installed.is_dir())
            stranger = Path(home) / 'Applications' / 'Throughline.app' / 'Contents'
            stranger.mkdir(parents=True)
            (stranger / 'Info.plist').write_text('<string>com.example.other</string>', encoding='utf-8')
            self.install(shared, home, writable=True)
            self.assertTrue(stranger.is_dir())


class Commands(unittest.TestCase):
    def test_both_commands_are_installed(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest('tomllib needs Python 3.11')
        root = Path(__file__).resolve().parent.parent
        scripts = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['scripts']
        self.assertEqual(scripts['guided-learning'], 'guided_learning.__main__:main')
        self.assertEqual(scripts['throughline'], 'guided_learning.__main__:throughline')

    def test_throughline_alone_opens_the_app_and_otherwise_is_guided_learning(self):
        from guided_learning import __main__ as entry
        with mock.patch.object(commands, 'main', return_value=0) as run:
            self.assertEqual(entry.throughline([]), 0)
            run.assert_called_once_with(['open'])
            run.reset_mock()
            entry.throughline(['stop'])
            run.assert_called_once_with(['stop'])


class Doctor(unittest.TestCase):
    FOUND = checks.result('codex', True, 'codex-cli 1.0 (/bin/codex)')

    def doctor(self, home, found, answer=None):
        output = io.StringIO()
        with mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': home, 'GUIDED_LEARNING_CONFIG': str(Path(home) / 's.json')}), \
                mock.patch.object(checks, 'codex_checks', return_value=found), \
                mock.patch.object(checks, 'probe_model', return_value='gpt-6-luna'), \
                mock.patch.object(checks, 'codex_answers', return_value=answer) as asked, \
                mock.patch.object(commands, 'launcher_path', return_value=Path(home) / 'throughline.desktop'), \
                mock.patch.object(commands, 'running', return_value=None), redirect_stdout(output):
            code = commands.main(['doctor'])
        return code, output.getvalue(), asked

    def test_all_good_names_the_model_and_how_long_it_took(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / 'throughline.desktop').write_text('', encoding='utf-8')
            answer = checks.result('answers', True, '', model='gpt-6-luna', seconds=2.4)
            code, output, asked = self.doctor(home, [self.FOUND], answer)
        self.assertEqual(code, 0, output)
        asked.assert_called_once_with('gpt-6-luna')
        self.assertIn(f'Throughline {commands.version()}', output)
        self.assertIn('ok    Codex: codex-cli 1.0 (/bin/codex)', output)
        self.assertIn('ok    Codex answers: gpt-6-luna replied in 2.4 s', output)
        self.assertIn(f'ok    Course library: {home}', output)
        self.assertIn('--    Throughline: not running', output)
        self.assertNotIn('FAIL', output)

    def test_failures_say_what_to_do_and_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as home:
            answer = checks.result('answers', False, '401 Unauthorized', model='gpt-6-luna', seconds=1.0)
            code, output, _ = self.doctor(home, [self.FOUND], answer)
        self.assertEqual(code, 1)
        self.assertIn('FAIL  Codex answers: 401 Unauthorized (gpt-6-luna, 1.0 s)\n'
                      '        Check that `codex` works in a terminal (signed in, or with an API key).', output)
        self.assertIn('FAIL  Launcher:', output)

    def test_without_codex_no_model_is_asked(self):
        with tempfile.TemporaryDirectory() as home:
            code, output, asked = self.doctor(home, [checks.result('codex', False)])
        self.assertEqual(code, 1)
        asked.assert_not_called()
        self.assertIn('FAIL  Codex: not found', output)


if __name__ == '__main__':
    unittest.main()
