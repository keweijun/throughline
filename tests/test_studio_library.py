"""Studio on the library page (#109): course work before a course is open, against the scripted App Server."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from support import call_cli
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings

FAKE = Path(__file__).resolve().parent / 'fake_studio_server.py'


class LibraryStudioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.library = (self.tmp / 'library').resolve()
        self.library.mkdir()
        self.log = self.tmp / 'server.log'
        app = create_app(library_root=self.library, runner=None, settings=TeacherSettings(self.tmp / 'config' / 'settings.json'),
                         studio_command=[sys.executable, str(FAKE), str(self.log)])
        self.client = TestClient(app, base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def received(self, method, titles=False):
        import json
        lines = self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []
        # A new chat's title is written on a side thread of its own, left out unless asked for.
        found = [json.loads(line)['params'] for line in lines if json.loads(line).get('method') == method]
        return [p for p in found if titles or not (p.get('ephemeral') or p.get('outputSchema'))]

    def threads(self, scope='library'):
        return [t['id'] for t in self.client.get('/api/studio', params={'scope': scope} if scope else {}).json()['threads']]

    def test_studio_works_on_the_library_page_before_any_course_is_open(self):
        # Without a scope, Studio still needs an open course.
        self.assertEqual(self.client.get('/api/studio').json()['code'], 'no_course')
        view = self.client.get('/api/studio', params={'scope': 'library'}).json()
        self.assertTrue(view['available'])
        self.assertEqual(view['threads'], [])

        sent = self.client.post('/api/studio/messages', params={'scope': 'library'}, json={'text': 'Make a course from these files'})
        self.assertEqual(sent.status_code, 200, sent.text)
        started = self.received('thread/start')[0]
        self.assertIn('no course open', started['developerInstructions'])
        self.assertIn('.intake/', started['developerInstructions'])
        turn = self.received('turn/start')[0]
        self.assertEqual(turn['sandboxPolicy']['writableRoots'], [str(self.library)])
        self.assertEqual(self.threads(), [sent.json()['thread']])

    def test_files_attached_on_the_library_page_wait_in_a_dated_intake_folder(self):
        uploaded = self.client.post('/api/studio/files', params={'name': 'lecture.pdf', 'scope': 'library'}, content=b'%PDF-1',
                                    headers={'content-type': 'application/pdf'}).json()
        today = time.strftime('%Y-%m-%d')
        self.assertEqual(uploaded['path'], f'.intake/{today}/lecture.pdf')
        self.assertEqual((self.library / '.intake' / today / 'lecture.pdf').read_bytes(), b'%PDF-1')
        # The intake folder is never listed as a course.
        self.assertEqual(self.client.get('/api/library').json()['courses'], [])
        image = self.client.post('/api/images', params={'scope': 'library'}, content=b'\x89PNG\r\n\x1a\n' + b'0' * 64,
                                 headers={'content-type': 'image/png'}).json()['image']
        self.assertEqual(self.client.get(f'/api/images/{image}', params={'scope': 'library'}).status_code, 200)

    def test_a_library_chat_that_made_a_course_moves_to_that_course(self):
        thread = self.client.post('/api/studio/messages', params={'scope': 'library'}, json={'text': 'Make a course'}).json()['thread']
        course = self.library / 'quantum'
        course.mkdir()
        call_cli(self, course, 'course.init', title='Quantum')
        moved = self.client.post(f'/api/studio/threads/{thread}/course', json={'name': 'quantum'})
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(self.threads(), [])
        self.client.post('/api/library/open', json={'name': 'quantum'})
        self.assertEqual(self.threads(scope=''), [thread])
        self.assertGreaterEqual(self.client.post(f'/api/studio/threads/{thread}/course', json={'name': 'nowhere'}).status_code, 400)

    def course(self, name, routed=True):
        course = self.library / name
        course.mkdir()
        call_cli(self, course, 'course.init', title=name.title())
        if routed:
            call_cli(self, course, 'curriculum.save', concepts=[{'id': 'a', 'title': 'A'}], route=['a'], coverage=[])
        return course

    def ended(self, thread):
        for _ in range(100):
            if thread not in self.client.get('/api/studio/activity', params={'scope': 'library'}).json()['running']:
                return
            time.sleep(0.05)
        self.fail(f'the turn in {thread} never ended')

    def test_a_library_chat_moves_into_the_course_it_made_even_when_no_page_watched_the_turn_end(self):
        # The host keeps the courses there were when the chat began, so a page reloaded or closed during a long build
        # does not decide whether the chat follows its course.
        self.course('optics')
        thread = self.client.post('/api/studio/messages', params={'scope': 'library'}, json={'text': 'Make a course'}).json()['thread']
        self.ended(thread)
        # A course without a route is still being made, and one that was there before is not this chat's.
        self.course('physics', routed=False)
        self.assertEqual(self.threads(), [thread])
        call_cli(self, self.library / 'physics', 'curriculum.save', concepts=[{'id': 'a', 'title': 'A'}], route=['a'], coverage=[])

        # Opening the course it made lists the chat there, with no library page asking to move it.
        self.client.post('/api/library/open', json={'name': 'physics'})
        self.assertEqual(self.threads(scope=''), [thread])
        self.assertEqual(self.threads(), [])
        self.client.post('/api/library/open', json={'name': 'optics'})
        self.assertEqual(self.threads(scope=''), [])

        # A library page still showing the chat reads it, and moving it there again changes nothing.
        history = self.client.get(f'/api/studio/threads/{thread}', params={'scope': 'library'}).json()
        self.assertEqual(history['courses_before'], ['optics'])
        self.assertEqual(self.client.post(f'/api/studio/threads/{thread}/course', json={'name': 'physics'}).status_code, 200)
        self.client.post('/api/library/open', json={'name': 'physics'})
        self.assertEqual(self.threads(scope=''), [thread])

    def test_a_library_chat_that_made_two_courses_waits_for_the_learner(self):
        thread = self.client.post('/api/studio/messages', params={'scope': 'library'}, json={'text': 'Make two courses'}).json()['thread']
        self.ended(thread)
        self.course('optics')
        self.course('physics')
        self.assertEqual(self.threads(), [thread])

    def test_a_library_chat_from_before_the_host_kept_its_courses_stays_in_the_library(self):
        import json
        config = self.tmp / 'config' / 'studio.json'
        thread = self.client.post('/api/studio/messages', params={'scope': 'library'}, json={'text': 'Make a course'}).json()['thread']
        self.ended(thread)
        data = json.loads(config.read_text(encoding='utf-8'))
        self.assertEqual(data['began'], {thread: []})
        del data['began']
        config.write_text(json.dumps(data), encoding='utf-8')
        self.course('optics')
        self.assertEqual(self.threads(), [thread])
        self.assertIsNone(self.client.get(f'/api/studio/threads/{thread}', params={'scope': 'library'}).json()['courses_before'])
        # Archiving a chat forgets what it began with.
        thread = self.client.post('/api/studio/messages', params={'scope': 'library'}, json={'text': 'Another'}).json()['thread']
        self.ended(thread)
        self.client.delete(f'/api/studio/threads/{thread}', params={'scope': 'library'})
        self.assertEqual(json.loads(config.read_text(encoding='utf-8'))['began'], {})


if __name__ == '__main__':
    unittest.main()
