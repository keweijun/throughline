"""Data a newer Throughline saved survives an older one writing beside it (the 1.0 promise, docs/stability.md)."""
import json
import tempfile
import unittest
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server.settings import Seen, TeacherSettings, write_json
from guided_learning.server.studio import Studio


class KeepsUnknownKeys(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def newer(self, name, data):
        path = self.tmp / name
        path.write_text(json.dumps({**data, 'from_a_newer_version': {'kept': True}}), encoding='utf-8')
        return path

    def kept(self, path):
        return json.loads(path.read_text(encoding='utf-8')).get('from_a_newer_version')

    def test_write_json_merges_and_leaves_no_temporary_file(self):
        path = self.newer('x.json', {'a': 1})
        self.assertEqual(write_json(path, {'a': 2}), {'a': 2, 'from_a_newer_version': {'kept': True}})
        self.assertEqual([p.name for p in self.tmp.iterdir()], ['x.json'])
        broken = self.tmp / 'broken.json'
        broken.write_text('[not an object', encoding='utf-8')
        self.assertEqual(write_json(broken, {'a': 1}), {'a': 1})

    def test_teacher_settings(self):
        path = self.newer('settings.json', {'model': 'old', 'effort': 'low'})
        TeacherSettings(path).save('gpt-x', 'high')
        self.assertEqual(self.kept(path), {'kept': True})
        self.assertEqual(json.loads(path.read_text())['model'], 'gpt-x')

    def test_dismissed_tips(self):
        path = self.newer('seen.json', {'seen': ['a']})
        Seen(path).add('b')
        self.assertEqual(self.kept(path), {'kept': True})
        self.assertEqual(json.loads(path.read_text())['seen'], ['a', 'b'])

    def test_studio_access_and_threads(self):
        path = self.newer('studio.json', {'full_access': False, 'courses': {}})
        studio = Studio(self.tmp, events=None, settings=TeacherSettings(self.tmp / 'settings.json'), path=path)
        studio.set_full_access(True)
        self.assertEqual(self.kept(path), {'kept': True})
        self.assertTrue(json.loads(path.read_text())['full_access'])

    def test_course_preferences(self):
        course = self.tmp / 'course'
        execute(course, {'op': 'course.init', 'title': 'Waves'})
        execute(course, {'op': 'preferences.save', 'language': 'en'})
        from guided_learning.store import Store
        store = Store(course)
        try:
            store.put('course', 'preferences', {'language': 'en', 'from_a_newer_version': 'kept'})
            store.db.commit()
        finally:
            store.db.close()
        saved = execute(course, {'op': 'preferences.save', 'language': 'zh-CN'})
        self.assertEqual(saved['preferences'], {'language': 'zh-CN'})  # the view shows what this version knows
        store = Store(course)
        try:
            self.assertEqual(store.get('course', 'preferences'), {'language': 'zh-CN', 'from_a_newer_version': 'kept'})
        finally:
            store.db.close()


if __name__ == '__main__':
    unittest.main()
