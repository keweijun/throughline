import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import httpx

from guided_learning.providers import CodexRunner, OpenAICompatibleRunner, ProviderError, ProviderSettings
from guided_learning.store import OperationError


def sse(*chunks):
    lines = [f'data: {json.dumps(c)}\n\n' for c in chunks] + ['data: [DONE]\n\n']
    return ''.join(lines).encode()


def delta(text):
    return {'choices': [{'delta': {'content': text}}]}


class OpenAICompatible(unittest.TestCase):
    def runner(self, handler, **options):
        return OpenAICompatibleRunner('http://provider.test/v1', 'teacher-model', api_key='secret', transport=httpx.MockTransport(handler), **options)

    def test_streams_deltas_then_authoritative_final_text(self):
        seen = {}

        def handler(request):
            seen['auth'] = request.headers['authorization']
            seen['path'] = request.url.path
            seen['body'] = json.loads(request.content)
            return httpx.Response(200, content=sse({'choices': [{'delta': {'role': 'assistant'}}]}, delta('Amplitudes '), delta('add.')),
                                  headers={'content-type': 'text/event-stream'})
        events = []
        self.runner(handler, effort='low').run('Teach', '.', events.append, threading.Event())
        self.assertEqual(events, [{'kind': 'delta', 'text': 'Amplitudes '}, {'kind': 'delta', 'text': 'add.'},
                                  {'kind': 'final', 'text': 'Amplitudes add.'}, {'kind': 'complete'}])
        self.assertEqual(seen['auth'], 'Bearer secret')
        self.assertEqual(seen['path'], '/v1/chat/completions')
        self.assertEqual(seen['body'], {'model': 'teacher-model', 'stream': True, 'reasoning_effort': 'low',
                                        'messages': [{'role': 'user', 'content': 'Teach'}]})

    def test_provider_errors_are_reported_without_completion(self):
        def handler(request):
            return httpx.Response(401, json={'error': {'message': 'Invalid API key'}})
        events = []
        with self.assertRaisesRegex(ProviderError, 'HTTP 401: Invalid API key'):
            self.runner(handler).run('Teach', '.', events.append, threading.Event())
        self.assertEqual(events, [])

    def test_empty_reply_is_not_a_completed_lesson(self):
        def handler(request):
            return httpx.Response(200, content=sse(), headers={'content-type': 'text/event-stream'})
        events = []
        with self.assertRaises(ProviderError):
            self.runner(handler).run('Teach', '.', events.append, threading.Event())
        self.assertEqual(events, [])

    def test_cancel_stops_a_slow_stream_without_completing(self):
        cancel = threading.Event()

        class Slow(httpx.SyncByteStream):
            def __iter__(self):
                yield f'data: {json.dumps(delta("Partial"))}\n\n'.encode()
                for _ in range(100):
                    time.sleep(.05)
                    yield b': waiting\n\n'
                yield f'data: {json.dumps(delta(" rest"))}\n\n'.encode()

        def handler(request):
            return httpx.Response(200, stream=Slow(), headers={'content-type': 'text/event-stream'})
        events = []

        def emit(event):
            events.append(event)
            cancel.set()
        started = time.monotonic()
        self.runner(handler).run('Teach', '.', emit, cancel)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(events, [{'kind': 'delta', 'text': 'Partial'}])

    def test_lists_models(self):
        def handler(request):
            self.assertEqual(request.url.path, '/v1/models')
            return httpx.Response(200, json={'data': [{'id': 'b-model'}, {'id': 'a-model'}, {'object': 'model'}]})
        self.assertEqual(self.runner(handler).list_models(), ['a-model', 'b-model'])


class Settings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'providers.json'

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_to_local_codex(self):
        settings = ProviderSettings(self.path)
        self.assertEqual(settings.public()['active'], 'codex')
        self.assertIsInstance(settings.runner(), CodexRunner)
        self.assertFalse(self.path.exists(), 'reading defaults never writes a settings file')

    def test_api_keys_are_stored_privately_and_never_public(self):
        settings = ProviderSettings(self.path)
        settings.upsert({'id': 'local-llm', 'kind': 'openai', 'base_url': 'http://127.0.0.1:11434/v1/', 'model': 'qwen3', 'api_key': 'sk-secret'})
        settings.activate('local-llm')
        public = settings.public()
        self.assertNotIn('sk-secret', json.dumps(public))
        provider = next(p for p in public['providers'] if p['id'] == 'local-llm')
        self.assertTrue(provider['has_api_key'])
        self.assertEqual(provider['base_url'], 'http://127.0.0.1:11434/v1')
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        settings.upsert({'id': 'local-llm', 'kind': 'openai', 'base_url': 'http://127.0.0.1:11434/v1', 'model': 'qwen3-large'})
        runner = settings.runner()
        self.assertEqual((runner.api_key, runner.model), ('sk-secret', 'qwen3-large'), 'saving without a key keeps the stored key')

    def test_key_from_environment_and_invalid_settings(self):
        settings = ProviderSettings(self.path)
        settings.upsert({'id': 'hosted', 'kind': 'openai', 'base_url': 'https://api.example.com/v1', 'model': 'm', 'api_key_env': 'GL_TEST_KEY'})
        os.environ['GL_TEST_KEY'] = 'from-env'
        try:
            self.assertEqual(settings.runner('hosted').api_key, 'from-env')
        finally:
            del os.environ['GL_TEST_KEY']
        for bad in ({'id': 'Bad Id', 'kind': 'openai', 'base_url': 'https://x'}, {'id': 'x', 'kind': 'other'},
                    {'id': 'x', 'kind': 'openai', 'base_url': 'ftp://x'}, {'id': 'x', 'kind': 'openai', 'base_url': 'https://x', 'api_key_env': 'not valid'}):
            with self.assertRaises(OperationError):
                settings.upsert(bad)

    def test_command_line_override_is_not_saved(self):
        ProviderSettings(self.path).upsert({'id': 'hosted', 'kind': 'openai', 'base_url': 'https://api.example.com/v1', 'model': 'saved'})
        settings = ProviderSettings(self.path, override={'provider': 'hosted', 'model': 'trial'})
        self.assertEqual(settings.active()['model'], 'trial')
        self.assertEqual(ProviderSettings(self.path).active()['id'], 'codex')
        with self.assertRaises(OperationError):
            ProviderSettings(self.path, override={'provider': 'missing'}).active()

    def test_last_provider_cannot_be_removed(self):
        settings = ProviderSettings(self.path)
        with self.assertRaises(OperationError):
            settings.remove('codex')


class EndToEnd(unittest.TestCase):
    def test_lesson_runs_through_a_local_openai_compatible_server(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from guided_learning.api import execute
        from guided_learning.server import Host
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = json.dumps({'data': [{'id': 'local-teacher'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                received.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                self.wfile.write(sse(delta('## Unit overview\n\n'), delta('Amplitudes add before squaring.')))

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op': 'course.init', 'title': 'Quantum'})
            execute(tmp, {'op': 'curriculum.save', 'concepts': [{'id': 'wave', 'title': 'Waves'}], 'route': ['wave'], 'coverage': []})
            settings = ProviderSettings(Path(tmp) / 'providers.json')
            base_url = f'http://127.0.0.1:{server.server_port}/v1'
            self.assertEqual(settings.draft_runner({'id': 'local', 'kind': 'openai', 'base_url': base_url}).list_models(), ['local-teacher'])
            settings.upsert({'id': 'local', 'kind': 'openai', 'base_url': base_url, 'model': 'local-teacher'})
            settings.activate('local')
            host = Host(tmp, settings=settings)
            try:
                host.start_lesson({'id': 'lesson'})
                turn = host.wait('lesson', 5)
            finally:
                host.close()
                server.shutdown()
            self.assertEqual(turn['status'], 'completed', turn.get('error'))
            self.assertEqual(turn['text'], '## Unit overview\n\nAmplitudes add before squaring.')
            self.assertEqual(received['model'], 'local-teacher')
            self.assertIn('Teach in English by default', received['messages'][0]['content'])


if __name__ == '__main__':
    unittest.main()
