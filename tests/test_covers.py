import tempfile
import unittest
from pathlib import Path

from guided_learning import covers, library
from guided_learning.api import execute
from support import call_cli


class Cover(unittest.TestCase):
    def test_a_course_starts_without_a_cover_and_keeps_the_one_saved(self):
        with tempfile.TemporaryDirectory() as path:
            call_cli(self, path, 'course.init', title='物理化学')
            listed = call_cli(self, path, 'cover.list')
            self.assertIsNone(listed['cover'])
            self.assertEqual([p['id'] for p in listed['patterns']], list(covers.PATTERNS))
            self.assertTrue(all(p['looks'] and p['subjects'] for p in listed['patterns']))
            self.assertNotIn('cover', call_cli(self, path, 'course.status'))
            saved = call_cli(self, path, 'cover.save', name='  物化 ', pattern='orbits')
            self.assertEqual(saved, {'cover': {'name': '物化', 'pattern': 'orbits'}})
            self.assertEqual(call_cli(self, path, 'course.status')['cover'], {'name': '物化', 'pattern': 'orbits'})
            call_cli(self, path, 'cover.save', name='P-Chem', pattern='waves')
            self.assertEqual(call_cli(self, path, 'cover.list')['cover'], {'name': 'P-Chem', 'pattern': 'waves'}, 'saving replaces the cover')

    def test_a_cover_that_cannot_be_drawn_is_refused_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as path:
            call_cli(self, path, 'course.init', title='Data Structures')
            call_cli(self, path, 'cover.save', name='DS', pattern='branches')
            error = call_cli(self, path, 'cover.save', error='unknown_pattern', name='DS', pattern='sparkles')
            self.assertIn('sparkles', error['error']['message'])
            for name in ('', '   ', 'Data\nStructures', 'Data Structures and Algorithms', 7):
                call_cli(self, path, 'cover.save', error='invalid_cover', name=name, pattern='branches')
            self.assertEqual(call_cli(self, path, 'cover.list')['cover'], {'name': 'DS', 'pattern': 'branches'})

    def test_the_library_lists_each_courses_cover(self):
        with tempfile.TemporaryDirectory() as root:
            with_cover, without = Path(root) / 'thermo', Path(root) / 'signals'
            execute(with_cover, {'op': 'course.init', 'title': 'Thermodynamics'})
            execute(with_cover, {'op': 'cover.save', 'name': 'Thermo', 'pattern': 'contours'})
            execute(without, {'op': 'course.init', 'title': 'Signals and Systems'})
            covers_by_name = {c['name']: c['cover'] for c in library.list_courses(root)}
            self.assertEqual(covers_by_name, {'thermo': {'name': 'Thermo', 'pattern': 'contours'}, 'signals': None})


if __name__ == '__main__':
    unittest.main()
