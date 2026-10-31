import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from guided_learning.server import create_app
from guided_learning.server.settings import Seen, TeacherSettings


class Idle:
    def run(self, prompt, cwd, emit, cancel):
        cancel.wait(3)


class SeenTests(unittest.TestCase):
    def test_marks_persist_once_each_and_survive_a_new_store(self):
        with tempfile.TemporaryDirectory() as config:
            path = Path(config) / 'nested' / 'seen.json'
            seen = Seen(path)
            self.assertEqual(seen.all(), [])
            self.assertEqual(seen.add('hint-select-passage'), ['hint-select-passage'])
            self.assertEqual(seen.add('hint-select-passage'), ['hint-select-passage'])
            seen.add('hint-citation')
            self.assertEqual(Seen(path).all(), ['hint-select-passage', 'hint-citation'])

    def test_an_unreadable_file_only_shows_things_again(self):
        with tempfile.TemporaryDirectory() as config:
            path = Path(config) / 'seen.json'
            path.write_text('not json', encoding='utf-8')
            self.assertEqual(Seen(path).all(), [])

    def test_api_keeps_seen_beside_the_settings_before_any_course_is_open(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as config:
            app = create_app(port=8765, runner=Idle(), settings=TeacherSettings(Path(config) / 's.json'), library_root=root)
            with TestClient(app, base_url='http://127.0.0.1:8765') as client:
                self.assertEqual(client.get('/api/seen').json(), {'seen': []})
                self.assertEqual(client.post('/api/seen', json={'id': 'hint-citation'}).json(), {'seen': ['hint-citation']})
                for bad in ('../escape', 'Hint', 'hint:citation', ''):
                    self.assertGreaterEqual(client.post('/api/seen', json={'id': bad}).status_code, 400, bad)
                self.assertEqual(client.get('/api/seen').json(), {'seen': ['hint-citation']})
            self.assertEqual(json.loads((Path(config) / 'seen.json').read_text())['seen'], ['hint-citation'])


if __name__ == '__main__':
    unittest.main()
