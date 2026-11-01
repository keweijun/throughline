"""Studio (ADR 0016): course work as a Codex chat over the App Server, tested against a scripted server."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from support import call_cli
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings
from guided_learning.server.studio import message_input

FAKE = Path(__file__).resolve().parent / 'fake_studio_server.py'


class StudioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.course = self.tmp / 'library' / 'waves'
        self.course.mkdir(parents=True)
        call_cli(self, self.course, 'course.init', title='Waves')
        self.log = self.tmp / 'server.log'
        self.client = self.open()

    def open(self, *extra, course=None):
        app = create_app(course or self.course, runner=None, settings=TeacherSettings(self.tmp / 'config' / 'settings.json'),
                         studio_command=[sys.executable, str(FAKE), str(self.log), *extra])
        client = TestClient(app, base_url='http://127.0.0.1:8765')
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return client

    def received(self, method):
        lines = self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []
        return [json.loads(line)['params'] for line in lines if json.loads(line).get('method') == method]

    def send(self, text, **body):
        response = self.client.post('/api/studio/messages', json={'text': text, **body})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def history(self, thread, until):
        for _ in range(100):
            history = self.client.get(f'/api/studio/threads/{thread}').json()
            if until(history):
                return history
            time.sleep(.05)
        self.fail(f'Studio thread never reached the expected state: {history}')

    @staticmethod
    def replies(history):
        return [i['text'] for t in history['turns'] for i in t['items'] if i['type'] == 'agentMessage']

    def test_a_message_starts_a_course_thread_that_writes_only_inside_the_library(self):
        sent = self.send('Add the new problem set')
        self.assertFalse(sent['steered'])
        history = self.history(sent['thread'], lambda h: self.replies(h) == ['done'])
        self.assertEqual(history['turns'][0]['items'][0]['content'][0]['text'], 'Add the new problem set')
        started = self.received('thread/start')[0]
        self.assertEqual((started['sandbox'], started['approvalPolicy'], started['ephemeral']), ('workspace-write', 'on-request', False))
        self.assertIn('Throughline Studio', started['developerInstructions'])
        self.assertIn('never run `guided-learning open`', started['developerInstructions'])
        turn = self.received('turn/start')[0]
        self.assertEqual(turn['approvalPolicy'], 'on-request')
        self.assertEqual(turn['sandboxPolicy']['type'], 'workspaceWrite')
        self.assertEqual(turn['sandboxPolicy']['writableRoots'], [str(self.course.resolve())])
        self.assertFalse(turn['sandboxPolicy']['networkAccess'])
        view = self.client.get('/api/studio').json()
        self.assertTrue(view['available'])
        self.assertEqual([t['id'] for t in view['threads']], [sent['thread']])
        self.assertEqual(view['threads'][0]['preview'], 'Add the new problem set')

    def test_full_access_drops_the_sandbox_and_the_prompts_from_the_next_turn(self):
        thread = self.send('first')['thread']
        self.history(thread, lambda h: self.replies(h) == ['done'] and not h['active_turn'])
        access = self.client.put('/api/studio/access', json={'full_access': True}).json()
        self.assertEqual(access, {'full_access': True, 'saved': True, 'forced': False})
        self.send('second', thread_id=thread)
        turn = self.received('turn/start')[-1]
        self.assertEqual((turn['approvalPolicy'], turn['sandboxPolicy']), ('never', {'type': 'dangerFullAccess'}))
        saved = json.loads((self.tmp / 'config' / 'studio.json').read_text())
        self.assertTrue(saved['full_access'])
        self.assertEqual(saved['courses'][str(self.course.resolve())], [thread])

    def test_an_approval_waits_for_the_learner_and_returns_their_decision(self):
        thread = self.send('please approve this')['thread']
        history = self.history(thread, lambda h: h['pending'])
        request = history['pending'][0]
        self.assertEqual(request['method'], 'item/commandExecution/requestApproval')
        self.assertEqual(request['params']['command'], 'touch ../outside')
        bad = self.client.post(f"/api/studio/requests/{request['id']}", json={'decision': 'maybe'})
        self.assertEqual(bad.status_code, 409)
        self.assertEqual(self.client.post(f"/api/studio/requests/{request['id']}", json={'decision': 'decline'}).status_code, 200)
        history = self.history(thread, lambda h: 'decision: decline' in self.replies(h))
        self.assertEqual(history['pending'], [])
        again = self.client.post(f"/api/studio/requests/{request['id']}", json={'decision': 'accept'})
        self.assertEqual(again.status_code, 404)

    def test_a_question_from_codex_is_answered_with_the_chosen_options(self):
        thread = self.send('ask me something')['thread']
        request = self.history(thread, lambda h: h['pending'])['pending'][0]
        self.assertEqual(request['params']['questions'][0]['question'], 'What for?')
        self.client.post(f"/api/studio/requests/{request['id']}", json={'answers': {'goal': ['Exam']}})
        history = self.history(thread, lambda h: any(r.startswith('answer:') for r in self.replies(h)))
        self.assertIn('answer: {"goal": {"answers": ["Exam"]}}', self.replies(history))

    def test_a_message_while_codex_works_steers_the_running_turn_and_stop_interrupts(self):
        thread = self.send('wait for more')['thread']
        self.history(thread, lambda h: h['active_turn'])
        steered = self.send('also add the solutions', thread_id=thread)
        self.assertTrue(steered['steered'])
        self.assertEqual(len(self.received('turn/start')), 1)
        self.history(thread, lambda h: 'steered: also add the solutions' in self.replies(h))
        self.send('wait again', thread_id=thread)
        self.history(thread, lambda h: h['active_turn'])
        self.client.post(f'/api/studio/threads/{thread}/interrupt')
        history = self.history(thread, lambda h: not h['active_turn'])
        self.assertEqual(history['turns'][-1]['status'], 'interrupted')

    def test_threads_can_be_renamed_and_archived(self):
        thread = self.send('hello')['thread']
        self.history(thread, lambda h: self.replies(h))
        self.client.put(f'/api/studio/threads/{thread}', json={'name': '  Chapter 3  '})
        self.assertEqual(self.received('thread/name/set')[0], {'threadId': thread, 'name': 'Chapter 3'})
        self.client.delete(f'/api/studio/threads/{thread}')
        self.assertEqual(self.client.get('/api/studio').json()['threads'], [])
        self.assertEqual(self.client.get(f'/api/studio/threads/{thread}').status_code, 404)

    def test_the_composer_lists_enabled_skills_and_course_files_but_not_the_course_database(self):
        skills = self.client.get('/api/studio/skills').json()['skills']
        self.assertEqual(skills, [{'name': 'throughline', 'path': '/skills/throughline/SKILL.md', 'title': 'Throughline',
                                   'description': 'Build a course'}])
        files = self.client.get('/api/studio/search', params={'q': 'wav'}).json()['files']
        self.assertEqual([f['path'] for f in files], ['inputs/waves.md'])
        self.assertEqual(files[0]['absolute'], str(self.course.resolve() / 'inputs' / 'waves.md'))

    def test_attached_files_are_copied_into_the_course_inputs_without_overwriting(self):
        first = self.client.post('/api/studio/files', params={'name': 'sheet.pdf'}, content=b'%PDF-1',
                                 headers={'content-type': 'application/pdf'}).json()
        second = self.client.post('/api/studio/files', params={'name': '../sheet.pdf'}, content=b'%PDF-2',
                                  headers={'content-type': 'application/pdf'}).json()
        self.assertEqual((first['path'], second['path']), ('inputs/sheet.pdf', 'inputs/sheet (2).pdf'))
        self.assertEqual((self.course / 'inputs' / 'sheet (2).pdf').read_bytes(), b'%PDF-2')

    def test_skills_files_and_images_go_to_codex_as_their_own_inputs(self):
        image = self.client.post('/api/images', content=b'\x89PNG\r\n\x1a\n' + b'0' * 64, headers={'content-type': 'image/png'}).json()['image']
        text = 'Ünit $throughline add @inputs/sheet.pdf'
        start = text.index('$')
        thread = self.send(text, elements=[{'start': start, 'end': start + 12}],
                           skills=[{'name': 'throughline', 'path': '/skills/throughline/SKILL.md'}],
                           mentions=[{'name': 'sheet.pdf', 'path': '/c/inputs/sheet.pdf'}], images=[image])['thread']
        self.history(thread, lambda h: self.replies(h))
        sent = self.received('turn/start')[0]['input']
        self.assertEqual(sent[0]['text_elements'], [{'byteRange': {'start': start + 1, 'end': start + 13}, 'placeholder': '$throughline'}])
        self.assertEqual([i['type'] for i in sent], ['text', 'skill', 'mention', 'localImage'])
        self.assertTrue(sent[3]['path'].endswith(image))

    def test_an_empty_message_is_refused(self):
        self.assertEqual(self.client.post('/api/studio/messages', json={'text': '  '}).status_code, 409)

    def test_a_hand_offs_context_goes_to_codex_as_its_own_input(self):
        thread = self.send('$throughline check this page', context='Chapter "Interference", source s1 page 4')['thread']
        self.history(thread, lambda h: self.replies(h))
        sent = self.received('turn/start')[0]['input']
        self.assertEqual(sent[1], {'type': 'text', 'text': 'Context from Throughline: Chapter "Interference", source s1 page 4', 'text_elements': []})

    def test_activity_names_the_threads_codex_works_in_or_waits_on_without_starting_codex(self):
        self.assertEqual(self.client.get('/api/studio/activity').json(), {'running': [], 'waiting': []})
        self.assertFalse(self.log.exists())  # asking did not start the App Server
        thread = self.send('please approve this')['thread']
        self.history(thread, lambda h: h['pending'])
        activity = self.client.get('/api/studio/activity').json()
        self.assertEqual(activity['running'], [thread])
        self.assertEqual([w['method'] for w in activity['waiting']], ['item/commandExecution/requestApproval'])

    def test_a_codex_without_the_methods_studio_needs_leaves_it_unavailable(self):
        other = self.tmp / 'library' / 'optics'
        other.mkdir()
        call_cli(self, other, 'course.init', title='Optics')
        client = self.open('old', course=other)
        view = client.get('/api/studio').json()
        self.assertFalse(view['available'])
        self.assertIn('newer Codex', view['error'])


class MessageInputTest(unittest.TestCase):
    def test_spans_are_counted_in_utf8_bytes_and_out_of_range_spans_dropped(self):
        items = message_input('数学 $s', [{'start': 3, 'end': 5}, {'start': 4, 'end': 99}])
        self.assertEqual(items[0]['text_elements'], [{'byteRange': {'start': 7, 'end': 9}, 'placeholder': '$s'}])

    def test_a_message_of_only_an_image_has_no_text_input(self):
        self.assertEqual(message_input(' ', images=['/a.png']), [{'type': 'localImage', 'path': '/a.png'}])


if __name__ == '__main__':
    unittest.main()
