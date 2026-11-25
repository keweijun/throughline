"""What still works under the names Throughline had before 0.66, when its command was guided-learning."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from throughline import library
from throughline.server import settings


class OldNames(unittest.TestCase):
    def test_the_old_library_variable_is_honoured_when_the_new_one_is_unset(self):
        with mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': '/old'}, clear=False):
            os.environ.pop('THROUGHLINE_HOME', None)
            self.assertEqual(library.default_root(), Path('/old'))
            self.assertEqual(library.legacy_roots(), [], 'a chosen library is never moved')
            with mock.patch.dict(os.environ, {'THROUGHLINE_HOME': '/new'}):
                self.assertEqual(library.default_root(), Path('/new'))


class ConfigFolder(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        env = {'XDG_CONFIG_HOME': str(self.base), 'APPDATA': str(self.base)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('THROUGHLINE_CONFIG', None)

    def test_the_old_folder_is_copied_once_and_left_in_place(self):
        old = self.base / 'guided-learning'
        old.mkdir()
        for name in ('settings.json', 'studio.json', 'seen.json'):
            (old / name).write_text(f'{{"from": "{name}"}}', encoding='utf-8')
        (old / 'settings.json.lock').write_text('', encoding='utf-8')
        self.assertEqual(settings.default_path(), self.base / 'throughline' / 'settings.json')
        new = self.base / 'throughline'
        self.assertEqual(sorted(p.name for p in new.iterdir()), ['seen.json', 'settings.json', 'studio.json'])
        self.assertEqual((new / 'studio.json').read_text(encoding='utf-8'), '{"from": "studio.json"}')
        self.assertTrue((old / 'settings.json').is_file(), 'an older version still finds its settings')
        (new / 'settings.json').write_text('{"model": "newer"}', encoding='utf-8')
        (old / 'settings.json').write_text('{"model": "older"}', encoding='utf-8')
        settings.default_path()
        self.assertEqual((new / 'settings.json').read_text(encoding='utf-8'), '{"model": "newer"}', 'copied only once')
        self.assertEqual([p.name for p in self.base.iterdir() if p.name.startswith('.')], [], 'no copy left half-done')

    def test_without_an_old_folder_nothing_is_made(self):
        settings.default_path()
        self.assertEqual(list(self.base.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
