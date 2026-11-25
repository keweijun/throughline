"""Two Throughline processes changing one per-user file at once keep both changes: each read, change and write holds
the file's lock (`throughline/userfiles.py`), so the later writer never replaces the file with a copy read before
the other's change."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from throughline import library
from throughline.api import execute
from throughline.server.settings import TeacherSettings
from throughline.server.studio import Studio

ROOT = Path(__file__).resolve().parents[1]
REAL_REPLACE = os.replace


class Interleaved(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def between_read_and_write(self, other):
        """Run `other` (Python source) in another process just before this process replaces the file it read, and let
        it run for a while: without a lock it writes in between; with one it waits until this process is done."""
        started = []

        def replace(source, target):
            if not started:
                process = subprocess.Popen([sys.executable, '-c', textwrap.dedent(other)], cwd=ROOT,
                                           env={**os.environ, 'PYTHONPATH': str(ROOT)})
                started.append(process)
                try:
                    process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    pass  # waiting on the lock this process holds
            return REAL_REPLACE(source, target)

        return mock.patch('os.replace', side_effect=replace), started

    def finish(self, started):
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0].wait(timeout=30), 0)

    def test_teacher_settings_keep_a_key_another_version_saved_meanwhile(self):
        path = self.tmp / 'settings.json'
        path.write_text(json.dumps({'model': 'old', 'effort': 'low'}), encoding='utf-8')
        patch, started = self.between_read_and_write(f"""
            from throughline.userfiles import write_json
            write_json({str(path)!r}, {{'from_a_newer_version': 'kept'}})
        """)
        with patch:
            TeacherSettings(path).save('gpt-x', 'high')
        self.finish(started)
        saved = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(saved['model'], 'gpt-x')
        self.assertEqual(saved.get('from_a_newer_version'), 'kept')

    def test_studio_keeps_chats_another_process_filed_meanwhile(self):
        path = self.tmp / 'studio.json'
        path.write_text(json.dumps({'courses': {'waves': ['t1']}}), encoding='utf-8')
        patch, started = self.between_read_and_write(f"""
            from throughline.server.settings import TeacherSettings
            from throughline.server.studio import Studio
            studio = Studio({str(self.tmp)!r}, events=None, settings=TeacherSettings({str(self.tmp / 's.json')!r}),
                            path={str(path)!r})
            studio._record('optics', 't2')
        """)
        studio = Studio(self.tmp, events=None, settings=TeacherSettings(self.tmp / 's.json'), path=path)
        with patch:
            studio._record('waves', 't3')
        self.finish(started)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['courses'],
                         {'waves': ['t3', 't1'], 'optics': ['t2']})

    def test_library_keeps_a_course_another_process_archived_meanwhile(self):
        root = self.tmp / 'library'
        for name in ('waves', 'optics'):
            execute(root / name, {'op': 'course.init', 'title': name.title()})
        patch, started = self.between_read_and_write(f"""
            from throughline import library
            library.set_archived({str(root)!r}, 'optics', True)
        """)
        with patch:
            library.set_archived(root, 'waves', True)
        self.finish(started)
        self.assertEqual(library.archived(root), {'waves', 'optics'})


if __name__ == '__main__':
    unittest.main()
