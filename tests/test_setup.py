"""Setup's last steps: opening the app, the welcome guide and where the launcher goes."""
import argparse
import errno
import io
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from throughline import checks, codex, commands


def setup_args(**options):
    return argparse.Namespace(**{'no_launcher': True, 'no_open': False, 'language': 'en', **options})


class SetupOpensTheApp(unittest.TestCase):
    def run_setup(self, home, **options):
        env = {'THROUGHLINE_HOME': home, 'THROUGHLINE_SKILLS_DIR': str(Path(home) / '.skills'),
               'THROUGHLINE_CONFIG': str(Path(home) / 'settings.json')}
        output = io.StringIO()
        with mock.patch.dict(os.environ, env), redirect_stdout(output):
            code = commands.setup(setup_args(**options))
        return code, output.getvalue()

    def test_setup_opens_the_library_and_says_so(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(commands, 'open_app', return_value=True) as opener:
            code, output = self.run_setup(home)
        self.assertEqual(code, 0)
        opener.assert_called_once_with('en')
        self.assertIn('Throughline is open in your browser', output)

    def test_the_library_opens_in_the_language_setup_was_run_in(self):
        # The page takes it for the library and the first-run series (ADR 0017).
        with tempfile.TemporaryDirectory() as home, mock.patch.object(commands, 'open_app', return_value=True) as opener:
            self.run_setup(home, language='zh-CN')
        opener.assert_called_once_with('zh-CN')

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


class SetupRemembersCodex(unittest.TestCase):
    def test_a_host_started_without_setups_path_finds_the_codex_setup_found(self):
        # A CLI-only install, set up from a terminal whose PATH has codex; Finder and Spotlight start the macOS
        # launcher with the system PATH only, so the host must not depend on that PATH.
        with tempfile.TemporaryDirectory() as home:
            cli = Path(home) / 'npm' / 'bin' / ('codex.exe' if os.name == 'nt' else 'codex')
            cli.parent.mkdir(parents=True)
            cli.write_text('')
            cli.chmod(0o755)
            env = {'THROUGHLINE_HOME': home, 'THROUGHLINE_SKILLS_DIR': str(Path(home) / '.skills'),
                   'THROUGHLINE_CONFIG': str(Path(home) / 'settings.json'), 'PATH': str(cli.parent),
                   'LOCALAPPDATA': str(Path(home) / 'no-app')}
            with mock.patch.dict(os.environ, env), mock.patch.object(commands, 'open_app', return_value=False), \
                    redirect_stdout(io.StringIO()) as output:
                os.environ.pop('CODEX_CLI_PATH', None)
                self.assertEqual(commands.setup(setup_args()), 0)
                self.assertNotIn('Codex was not found', output.getvalue())
                os.environ['PATH'] = str(Path(home) / 'system')  # the launcher's PATH
                with mock.patch.object(codex.os.path, 'expanduser', return_value=str(Path(home) / 'no-app')):
                    found = codex.find_codex()
            self.assertIsNotNone(found, 'the launcher lost the codex setup found')
            self.assertEqual(os.path.normcase(found), os.path.normcase(str(cli)))

class Welcome(unittest.TestCase):
    def test_the_guide_is_short_and_current(self):
        for language in commands.LANGUAGES:
            text = commands.welcome(Path('/courses'), Path('/x/throughline.desktop'), language, opened=True)
            self.assertIn(commands.version(), text)
            self.assertIn(str(Path('/courses')), text)
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
    def test_the_commands_are_installed_with_the_old_name_for_older_updaters(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest('tomllib needs Python 3.11')
        root = Path(__file__).resolve().parent.parent
        scripts = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['scripts']
        self.assertEqual(scripts['throughline'], 'throughline.__main__:throughline')
        self.assertEqual(scripts['guided-learning'], 'throughline.__main__:main', 'the name before 0.66, which older updaters run')
        self.assertEqual(scripts['throughline-web'], 'throughline.web:main')

    def test_throughline_alone_opens_the_app_and_otherwise_runs_the_command(self):
        from throughline import __main__ as entry
        with mock.patch.object(commands, 'main', return_value=0) as run:
            self.assertEqual(entry.throughline([]), 0)
            run.assert_called_once_with(['open'])
            run.reset_mock()
            entry.throughline(['stop'])
            run.assert_called_once_with(['stop'])


class MovingOldLibraries(unittest.TestCase):
    """Setup moves courses from where earlier versions kept them, but never one a host still has open."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.old, self.root = self.home / 'old', self.home / 'library'
        self.root.mkdir()
        for name in ('waves', 'optics'):
            (self.old / name).mkdir(parents=True)
            (self.old / name / 'course.sqlite3').write_bytes(b'')
        patches = (mock.patch.object(commands.library, 'legacy_roots', return_value=[self.old]),
                   mock.patch.object(commands, 'SHUTDOWN_WAIT', 0.2))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_course_a_host_still_holds_is_left_with_the_old_librarys_bookkeeping(self):
        (self.old / '.throughline').mkdir()
        (self.old / '.throughline' / 'host.json').write_text('{"port": 9}', encoding='utf-8')  # a host that does not answer
        held = commands.library.acquire_lease(self.old / 'optics')
        self.addCleanup(held.close)
        moved, skipped = commands.migrate(self.root)
        self.assertEqual((moved, skipped), (['waves'], [str(self.old / 'optics')]))
        self.assertTrue((self.root / 'waves' / 'course.sqlite3').is_file())
        self.assertTrue((self.old / 'optics' / 'course.sqlite3').is_file())
        self.assertTrue((self.old / '.throughline' / 'host.json').is_file(), 'the host that holds optics is still recorded')

    def test_a_course_setup_cannot_open_is_left_where_it_is(self):
        real = commands.library.acquire_lease

        def refuse(workspace):
            if workspace.name == 'optics':
                raise PermissionError('read-only')
            return real(workspace)
        with mock.patch.object(commands.library, 'acquire_lease', refuse):
            moved, skipped = commands.migrate(self.root)
        self.assertEqual((moved, skipped), (['waves'], [str(self.old / 'optics')]))

    def test_the_old_librarys_trash_and_archive_come_along(self):
        deleted = commands.library.trash_dir(self.old) / '20261101-120000-abcdef'
        (deleted / 'atoms').mkdir(parents=True)
        (deleted / 'atoms' / 'course.sqlite3').write_bytes(b'')
        (deleted / 'deleted.json').write_text('{"name": "atoms"}', encoding='utf-8')
        commands.library.set_archived(self.old, 'optics', True)
        moved, skipped = commands.migrate(self.root)
        self.assertEqual((sorted(moved), skipped), (['optics', 'waves'], []))
        self.assertTrue((commands.library.trash_dir(self.root) / deleted.name / 'atoms' / 'course.sqlite3').is_file(),
                        'a deleted course stays restorable')
        self.assertEqual(commands.library.archived(self.root), {'optics'})
        self.assertFalse(self.old.exists())

    def test_what_setup_does_not_know_in_the_old_librarys_own_folder_stays(self):
        own = commands.library.own_dir(self.old)
        own.mkdir()
        (own / 'host.json').write_text('{}', encoding='utf-8')
        (own / 'someone-elses.txt').write_text('keep me', encoding='utf-8')
        commands.migrate(self.root)
        self.assertFalse((own / 'host.json').exists())
        self.assertEqual((own / 'someone-elses.txt').read_text(encoding='utf-8'), 'keep me')

    def test_an_emptied_old_library_is_removed(self):
        moved, skipped = commands.migrate(self.root)
        self.assertEqual((sorted(moved), skipped), (['optics', 'waves'], []))
        self.assertFalse(self.old.exists())

    def test_a_write_running_when_setup_moves_a_course_finishes_first(self):
        writer = sqlite3.connect(self.old / 'waves' / 'course.sqlite3')
        writer.execute('BEGIN IMMEDIATE')  # Codex registering a source from the command line, halfway through
        moving = threading.Thread(target=commands.migrate, args=(self.root,))
        moving.start()
        moving.join(0.5)
        self.assertTrue((self.old / 'waves' / 'course.sqlite3').is_file(), 'the course waits for the write')
        writer.rollback()
        writer.close()
        moving.join(10)
        self.assertTrue((self.root / 'waves' / 'course.sqlite3').is_file())
        self.assertFalse((self.root / 'waves' / '.moving').exists(), 'a moved course takes writes')
        self.assertFalse(self.old.exists())

    def test_a_course_whose_move_is_refused_stays_whole_where_it_was(self):
        # Windows refuses to move a folder holding an open file.
        rename, replace = os.rename, os.replace

        def refuse(real):
            def move(source, target, *args, **kwargs):
                if Path(source).name == 'optics':
                    raise PermissionError(13, 'The process cannot access the file', str(source))
                return real(source, target, *args, **kwargs)
            return move
        with mock.patch('os.rename', refuse(rename)), mock.patch('os.replace', refuse(replace)):
            moved, skipped = commands.migrate(self.root)
        self.assertEqual((moved, skipped), (['waves'], [str(self.old / 'optics')]))
        self.assertTrue((self.old / 'optics' / 'course.sqlite3').is_file())
        self.assertFalse((self.old / 'optics' / '.moving').exists(), 'the course left behind still takes writes')
        self.assertFalse((self.root / 'optics').exists(), 'no half copy in the library')

    def test_a_course_moved_between_disks_is_copied_whole(self):
        replace = os.replace

        def across(source, target, *args, **kwargs):
            if Path(source).parent == self.old and Path(target).parent != self.old:
                raise OSError(errno.EXDEV, 'Invalid cross-device link')
            return replace(source, target, *args, **kwargs)
        with mock.patch('os.replace', across):
            moved, skipped = commands.migrate(self.root)
        self.assertEqual((sorted(moved), skipped), (['optics', 'waves'], []))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['optics', 'waves'])
        self.assertFalse((self.root / 'waves' / '.moving').exists())
        self.assertFalse(self.old.exists())

    def test_only_the_courses_an_old_librarys_archive_list_names_are_archived(self):
        # Two old libraries each hold a course named waves; only the second archived its own, which setup leaves
        # behind because the first one's took the name.
        second = self.home / 'second'
        (second / 'waves').mkdir(parents=True)
        (second / 'waves' / 'course.sqlite3').write_bytes(b'')
        commands.library.set_archived(second, 'waves', True)
        with mock.patch.object(commands.library, 'legacy_roots', return_value=[self.old, second]):
            moved, skipped = commands.migrate(self.root)
        self.assertEqual((sorted(moved), skipped), (['optics', 'waves'], [str(second / 'waves')]))
        self.assertEqual(commands.library.archived(self.root), set(), 'the waves that moved was never archived')


class Doctor(unittest.TestCase):
    FOUND = checks.result('codex', True, 'codex-cli 1.0 (/bin/codex)')

    def doctor(self, home, found, answer=None):
        output = io.StringIO()
        with mock.patch.dict(os.environ, {'THROUGHLINE_HOME': home, 'THROUGHLINE_CONFIG': str(Path(home) / 's.json')}), \
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
