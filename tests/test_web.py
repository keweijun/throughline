import tempfile
import unittest
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server import Host
from guided_learning.store import OperationError
from support import host_client


class BlockingRunner:
    def run(self, prompt, cwd, emit, cancel):
        cancel.wait(3)


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})


class WebLearning(unittest.TestCase):
    def test_existing_course_stream_record_and_browser_origin_boundary(self):
        class Runner:
            def run(self, prompt, cwd, emit, cancel):
                if not hasattr(self, 'prompt'):
                    self.prompt = prompt
                emit({'kind': 'delta', 'text': 'Lesson'})
                emit({'kind': 'final', 'text': 'Authoritative lesson.'})
                emit({'kind': 'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            runner = Runner()
            client, host = host_client(tmp, runner=runner)
            with client:
                response = client.post('/api/lessons', json={'id': 'one', 'prompt': 'Explain the state'})
                self.assertEqual(response.status_code, 200, response.text)
                host.wait('one', 5)
                state = client.get('/api/state').json()
                lesson = next(t for t in state['turns'] if t['id'] == 'one')
                self.assertEqual(lesson['status'], 'completed')
                self.assertEqual(lesson['title'], 'States')
                self.assertNotIn('prompt_snapshot', lesson)
                self.assertEqual(state['position']['concept_id'], 'state', 'starting without a position enters the first concept')
                self.assertIn('Authoritative lesson.', [i['text'] for i in state['session']['recent_interactions']])
                self.assertIn('States', runner.prompt)
                self.assertIn('sources', runner.prompt)
                self.assertIn('Teach in English by default', runner.prompt)
                self.assertIn('Use another language when the learner explicitly requests it', runner.prompt)
                denied = client.post('/api/lessons', json={'id': 'evil'}, headers={'Origin': 'https://evil.example'})
                self.assertEqual(denied.status_code, 403)
                self.assertEqual(client.get('/api/state', headers={'Host': 'evil.example'}).status_code, 403)

    def test_request_body_bounds_and_json_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            client, host = host_client(tmp, runner=BlockingRunner())
            with client:
                too_large = client.post('/api/questions', content=b'{}', headers={'Content-Type': 'application/json', 'Content-Length': str(2 * 1024 * 1024)})
                self.assertEqual(too_large.status_code, 413)
                form = client.post('/api/questions', content=b'question=x', headers={'Content-Type': 'application/x-www-form-urlencoded'})
                self.assertEqual(form.status_code, 415)
                invalid = client.post('/api/questions', json={'unexpected': True})
                self.assertEqual(invalid.status_code, 400)

    def test_two_mainline_generations_cannot_overlap_even_when_resuming(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            app = Host(tmp, runner=BlockingRunner())
            try:
                app.start_turn({'id': 'old', 'concept_id': 'state', 'prompt': 'Lesson'})
                app.pause_turn('old')
                app.wait('old', 2)
                app.start_turn({'id': 'new', 'concept_id': 'state', 'prompt': 'Other lesson'})
                with self.assertRaises(OperationError):
                    app.resume_turn('old', 'r1')
            finally:
                app.close()

    def test_second_host_cannot_mark_a_live_host_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            app = Host(tmp, runner=BlockingRunner())
            try:
                app.start_turn({'id': 'one', 'concept_id': 'state', 'prompt': 'Lesson'})
                with self.assertRaises(OperationError):
                    Host(tmp, runner=BlockingRunner())
                self.assertEqual(app.operation({'op': 'stream.read', 'id': 'one'})['turn']['status'], 'running')
            finally:
                app.close()

    def test_cross_origin_posts_consistently_receive_403_without_applying_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            execute(tmp, {'op': 'mainline.enter', 'concept_id': 'state', 'goal': 'g', 'next_step': 'n', 'request_id': 'p'})
            client, host = host_client(tmp, runner=BlockingRunner())
            with client:
                for _ in range(20):
                    response = client.post('/api/questions', json={'question': 'x' * 65536}, headers={'Origin': 'https://evil.example'})
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()['error'], 'Invalid local origin')
                self.assertEqual(host.questions.list(), [])

    def test_live_events_carry_lesson_deltas(self):
        class Runner:
            def run(self, prompt, cwd, emit, cancel):
                if 'Practice' in prompt.split('Current learner request:')[-1]:
                    return
                emit({'kind': 'delta', 'text': 'Hello '})
                emit({'kind': 'final', 'text': 'Hello lesson.'})
                emit({'kind': 'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            host = Host(tmp, runner=Runner())
            seen = []
            import asyncio

            async def collect():
                subscriber = host.events.subscribe()
                await asyncio.to_thread(host.start_lesson, {'id': 'live'})
                while True:
                    event = await asyncio.wait_for(subscriber[1].get(), 5)
                    seen.append(event)
                    if event['type'] == 'turn' and event['turn']['id'] == 'live' and event['turn']['status'] == 'completed':
                        return
            try:
                asyncio.run(collect())
            finally:
                host.close()
            self.assertIn({'type': 'delta', 'id': 'live', 'attempt': 1, 'text': 'Hello '}, seen)
            self.assertEqual(seen[0]['type'], 'turn')
            self.assertEqual(seen[0]['turn']['status'], 'running')

    def test_teacher_settings_apply_to_the_next_codex_request(self):
        from guided_learning.codex import CodexRunner
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            client, host = host_client(tmp, runner=BlockingRunner())
            with client:
                self.assertEqual(client.get('/api/state').json()['settings']['effort'], 'medium')
                saved = client.put('/api/settings', json={'model': 'gpt-6.1-sol', 'effort': 'high'})
                self.assertEqual((saved.json()['model'], saved.json()['effort']), ('gpt-6.1-sol', 'high'))
                runner = host.settings.runner()
                self.assertIsInstance(runner, CodexRunner)
                self.assertEqual((runner.model, runner.effort), ('gpt-6.1-sol', 'high'))
                self.assertEqual(client.put('/api/settings', json={'effort': 'extreme'}).status_code, 409)
                self.assertEqual(client.put('/api/settings', json={'base_url': 'https://x'}).status_code, 400)

    def test_command_line_choice_is_not_saved(self):
        from guided_learning.server.settings import TeacherSettings
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            TeacherSettings(path).save('saved-model', 'low')
            once = TeacherSettings(path, override={'model': 'trial', 'effort': None})
            self.assertEqual(once.current(), {'model': 'trial', 'effort': 'low'})
            self.assertEqual(TeacherSettings(path).current()['model'], 'saved-model')
            self.assertEqual(TeacherSettings(Path(tmp) / 'missing.json').current(), {'model': '', 'effort': 'medium'})


if __name__ == '__main__':
    unittest.main()
