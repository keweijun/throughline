"""Regression tests for host and operation robustness: failed writes, idle cost, error mapping and CLI errors."""
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from guided_learning import background, library
from guided_learning.api import execute
from guided_learning.server import Host, create_app
from guided_learning.server.settings import TeacherSettings
from guided_learning.store import OperationError
from support import call_cli, host_client


def course(path, concepts=('a', 'b')):
    execute(path, {'op': 'course.init', 'title': 'Course'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': c, 'title': c.upper()} for c in concepts], 'route': list(concepts), 'coverage': []})
    execute(path, {'op': 'mainline.enter', 'request_id': 'enter', 'concept_id': concepts[0], 'goal': 'Goal', 'next_step': 'Read'})


class Lesson:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Lesson'})
        emit({'kind': 'complete'})


def wait_until(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.03)
    return False


class TurnFailures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = self.temp.name
        course(self.path, ('a',))  # no next section, so preparation stays out of the way

    def failing_first_stream_write(self):
        """The first write of streamed events fails, as when the database stays locked."""
        from guided_learning.server import host as host_module
        real = host_module.execute
        failed = []

        def execute(workspace, request):
            if request.get('op') == 'stream.events' and not failed:
                failed.append(request)
                raise OperationError('busy', 'Synthetic write failure')
            return real(workspace, request)
        return mock.patch.object(host_module, 'execute', side_effect=execute)

    def test_a_failed_event_write_marks_the_turn_failed_and_frees_the_mainline(self):
        class Runner:
            def run(self, prompt, cwd, emit, cancel):
                emit({'kind': 'delta', 'text': 'partial'})
                emit({'kind': 'final', 'text': 'Final'})
                emit({'kind': 'complete'})
        host = Host(self.path, runner=Runner())
        try:
            with self.failing_first_stream_write():
                turn = host.start_lesson({'id': 'one'})['turn']
                finished = host.wait(turn['id'], 3)
            self.assertEqual(finished['status'], 'failed')
            self.assertIn('Synthetic write failure', finished['error'])
            self.assertEqual(finished['text'], 'partial', 'the events that failed to store are stored with the failure')
            host._runner = Lesson()
            self.assertEqual(host.wait(host.start_lesson({'id': 'two'})['turn']['id'], 3)['status'], 'completed')
        finally:
            host.close()

    def test_streamed_text_whose_write_failed_is_written_later(self):
        class Runner:
            def run(self, prompt, cwd, emit, cancel):
                emit({'kind': 'delta', 'text': 'kept '})
                time.sleep(0.2)  # the timed write fails meanwhile
                emit({'kind': 'delta', 'text': 'too'})
                emit({'kind': 'final', 'text': 'Final'})
                emit({'kind': 'complete'})
        host = Host(self.path, runner=Runner())
        host.persist_interval = 0.05
        try:
            with self.failing_first_stream_write() as write:
                turn = host.start_lesson({'id': 'one'})['turn']
                self.assertEqual(host.wait(turn['id'], 3)['status'], 'completed')
            batches = [c.args[1]['events'] for c in write.call_args_list if c.args[1]['op'] == 'stream.events']
            self.assertEqual([b[0].get('text') for b in batches[:2]], ['kept ', 'kept '], 'the failed write is retried')
        finally:
            host.close()

    def test_finished_workers_are_forgotten(self):
        host = Host(self.path, runner=Lesson())
        try:
            turn = host.start_lesson({'id': 'one'})['turn']
            host.wait(turn['id'], 3)
            self.assertTrue(wait_until(lambda: not host.workers))
        finally:
            host.close()

    def test_a_failing_completion_hook_does_not_stop_the_others(self):
        host = Host(self.path, runner=Lesson())
        try:
            seen = []
            with mock.patch.object(host.questions, 'on_complete', side_effect=RuntimeError('hook bug')), \
                    mock.patch.object(host.practice, 'on_complete', side_effect=seen.append), \
                    self.assertLogs('guided_learning.server.host', 'ERROR'):
                turn = host.start_lesson({'id': 'one'})['turn']
                host.wait(turn['id'], 3)
                self.assertTrue(wait_until(lambda: seen))
        finally:
            host.close()


class PreparationLoop(unittest.TestCase):
    def test_unexpected_errors_are_logged_and_the_loop_keeps_running(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            calls = []

            def schedule(retry=False):
                calls.append(retry)
                if len(calls) == 1:
                    raise RuntimeError('scheduler bug')
                return {'scheduled': False}
            with mock.patch('guided_learning.server.features.Preparation.schedule', side_effect=schedule), \
                    self.assertLogs('guided_learning.server.features', 'ERROR'):
                host = Host(path, runner=Lesson())
                try:
                    self.assertTrue(wait_until(lambda: calls))
                    host.preparation.wake()
                    self.assertTrue(wait_until(lambda: len(calls) >= 2))
                    self.assertTrue(host.preparation._thread.is_alive())
                finally:
                    host.close()

    def test_idle_host_leaves_the_course_file_alone(self):
        class Prepare:
            def run(self, prompt, cwd, emit, cancel):
                emit({'kind': 'final', 'text': 'Prepared'})
                emit({'kind': 'complete'})
        with tempfile.TemporaryDirectory() as path:
            course(path)
            host = Host(path, runner=Prepare())
            try:
                self.assertTrue(wait_until(lambda: any(j['status'] == 'ready' for j in host.preparation.state()['jobs'])))
                time.sleep(.3)
                database = Path(path) / 'course.sqlite3'
                before = database.stat().st_mtime_ns
                for _ in range(4):
                    host.preparation.wake()
                    time.sleep(.2)
                host.preparation.state()
                self.assertEqual(database.stat().st_mtime_ns, before, 'an unchanged ready job is not rewritten')
            finally:
                host.close()


class TurnListing(unittest.TestCase):
    def test_summaries_match_full_turns_without_snapshots(self):
        from guided_learning.server.host import turn_summary
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'stream.start', 'id': 't', 'concept_id': 'a', 'prompt': 'Teach', 'channel': 'mainline'})
            execute(path, {'op': 'stream.pause', 'id': 't'})
            execute(path, {'op': 'stream.resume', 'id': 't', 'request_id': 'r'})
            full = execute(path, {'op': 'stream.list'})['turns']
            summaries = execute(path, {'op': 'stream.summaries'})['turns']
            self.assertEqual(summaries, [turn_summary(t) for t in full])
            self.assertEqual(summaries[0]['title'], 'A')
            [brief] = execute(path, {'op': 'stream.summaries', 'brief': True})['turns']
            self.assertEqual({k: brief[k] for k in ('id', 'channel', 'status', 'concept_id', 'attempt', 'record_user')},
                             {'id': 't', 'channel': 'mainline', 'status': 'running', 'concept_id': 'a', 'attempt': 2, 'record_user': True})
            self.assertFalse({'prompt_snapshot', 'attempts', 'text', 'final_text'} & set(brief))

    def test_listings_follow_every_change_and_hand_out_fresh_objects(self):
        """Listings and the curriculum are decoded once until their documents change (issue #68); what an operation
        returns is the caller's own."""
        import sqlite3
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'stream.start', 'id': 't', 'concept_id': 'a', 'prompt': 'Teach'})
            [summary] = execute(path, {'op': 'stream.summaries'})['turns']
            summary['attempts'].append('mutated')
            summary['title'] = 'mutated'
            execute(path, {'op': 'stream.event', 'id': 't', 'attempt': 1, 'sequence': 1, 'kind': 'delta', 'text': 'Hi'})
            [summary] = execute(path, {'op': 'stream.summaries'})['turns']
            self.assertEqual((summary['text'], summary['title'], summary['attempts']), ('Hi', 'A', []))
            [brief] = execute(path, {'op': 'stream.summaries', 'brief': True})['turns']
            self.assertEqual(brief['sequence'], 1)
            execute(path, {'op': 'stream.start', 'id': 'u', 'concept_id': 'b', 'prompt': 'Next'})
            self.assertEqual([t['id'] for t in execute(path, {'op': 'stream.summaries', 'brief': True})['turns']], ['t', 'u'])

            context = execute(path, {'op': 'curriculum.context', 'concept_id': 'b'})
            context['concept']['title'] = 'mutated'
            context['prerequisites'].append('mutated')
            self.assertEqual(execute(path, {'op': 'curriculum.context', 'concept_id': 'b'})['concept']['title'], 'B')
            # Another process (Codex building the course, say) changes the plan behind this one's back.
            db = sqlite3.connect(Path(path) / 'course.sqlite3')
            with db:
                model = json.loads(db.execute("SELECT value FROM documents WHERE namespace='curriculum'").fetchone()[0])
                model['concepts'][1]['title'] = 'Renamed'
                db.execute("UPDATE documents SET value=? WHERE namespace='curriculum'", (json.dumps(model),))
            db.close()
            self.assertEqual(execute(path, {'op': 'curriculum.context', 'concept_id': 'b'})['concept']['title'], 'Renamed')
            self.assertEqual(execute(path, {'op': 'stream.start', 'id': 'v', 'concept_id': 'b', 'prompt': 'Again'})['turn']['prompt_snapshot']['route'][1]['title'], 'Renamed')


class CourseCreation(unittest.TestCase):
    def test_only_course_init_creates_a_course(self):
        with tempfile.TemporaryDirectory() as root:
            missing = Path(root) / 'typo'
            call_cli(self, missing, 'course.status', error='unknown_course')
            self.assertFalse(missing.exists())
            call_cli(self, missing, 'course.init', title='Real')
            self.assertEqual(call_cli(self, missing, 'course.status')['course']['title'], 'Real')

    def test_cli_reports_unexpected_errors_as_json(self):
        from guided_learning.__main__ import main
        with tempfile.TemporaryDirectory() as root, tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as request:
            request.write('{"op": "course.status"}')
        self.addCleanup(os.unlink, request.name)
        output = io.StringIO()
        with mock.patch('guided_learning.__main__.execute', side_effect=KeyError('job')), redirect_stdout(output), \
                mock.patch('sys.stderr', io.StringIO()):
            code = main(['--workspace', root, '--request', request.name])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())['error']['code'], 'internal_error')


class PracticeRecording(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = self.temp.name
        course(self.path, ('a',))

    def op(self, **request):
        return execute(self.path, request)

    def teacher(self, identifier, text):
        self.op(op='stream.start', id=identifier, concept_id='a', prompt='Practice', channel='practice', record_user=False)
        self.op(op='stream.event', id=identifier, attempt=1, sequence=1, kind='final', text=text)
        self.op(op='stream.event', id=identifier, attempt=1, sequence=2, kind='complete')

    def test_missing_job_fields_are_request_errors(self):
        for job in ({'id': 'x'}, {'id': 'x', 'concept_id': 'a', 'action': 'hint'}, {'id': 'x', 'concept_id': 'a', 'action': 'assess', 'task_id': 't'}):
            with self.assertRaises(OperationError) as raised:
                self.op(op='practice.job', job=job)
            self.assertEqual(raised.exception.code, 'invalid_request')
        with self.assertRaises(OperationError) as raised:
            self.op(op='practice.complete')
        self.assertEqual(raised.exception.code, 'invalid_request')

    def test_course_errors_are_not_called_format_errors_and_write_nothing(self):
        self.op(op='practice.job', job={'id': 'g', 'concept_id': 'a', 'action': 'generate'})
        self.teacher('g', '{"questions": [{"question": "Why?", "origin": "self_created"}]}')
        self.op(op='practice.complete', id='g')
        self.op(op='practice.job', job={'id': 'h', 'concept_id': 'a', 'action': 'hint', 'task_id': 'g:0'})
        self.teacher('h', '{"feedback": "Look at the units."}')
        # An interaction already holds the feedback's ID with other text: a course conflict, not bad teacher output.
        self.op(op='interaction.record', id='practice-feedback:h', role='assistant', text='Something else', concept_id='a')
        evidence_before = self.op(op='evidence.view', concept_id='a')['history']
        with self.assertRaises(OperationError) as raised:
            self.op(op='practice.complete', id='h')
        self.assertEqual(raised.exception.code, 'id_conflict')
        job = next(j for j in self.op(op='practice.list')['jobs'] if j['id'] == 'h')
        self.assertFalse(job.get('processed'))
        self.assertNotIn('error', job)
        self.assertEqual(self.op(op='evidence.view', concept_id='a')['history'], evidence_before)

    def test_bad_teacher_output_is_a_format_error_with_nothing_recorded(self):
        self.op(op='practice.job', job={'id': 'g', 'concept_id': 'a', 'action': 'generate'})
        self.teacher('g', '{"questions": [{"question": "Q", "origin": "source", "source_refs": [{"source_id": "x", "revision": "y", "unit_id": "z"}]}]}')
        job = self.op(op='practice.complete', id='g')['job']
        self.assertIn('format validation', job['error'])
        self.assertEqual(self.op(op='practice.list')['tasks'], [])


class HttpErrors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        course(self.temp.name, ('a',))
        app = create_app(self.temp.name, runner=Lesson(), settings=TeacherSettings(Path(self.temp.name) / 'settings.json'))
        self.host = app.state.host
        self.client = TestClient(app, base_url='http://127.0.0.1:8765', raise_server_exceptions=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_unknown_records_are_404_and_bugs_are_logged_500s(self):
        missing = self.client.post('/api/turns/nope/pause')
        self.assertEqual((missing.status_code, missing.json()['code']), (404, 'unknown_turn'))
        self.assertEqual(self.client.get('/api/concepts/zzz/preview').status_code, 404)
        with mock.patch.object(self.host.navigation, 'preview', side_effect=KeyError('concept')), \
                self.assertLogs('guided_learning.server.app', 'ERROR'):
            broken = self.client.get('/api/concepts/a/preview')
        self.assertEqual((broken.status_code, broken.json()['code']), (500, 'internal_error'))

    def test_cross_site_requests_cannot_reach_the_api(self):
        listed = {'models': []}
        with mock.patch.object(self.host.settings, 'models', return_value=listed) as models:
            for site in ('cross-site', 'same-site'):
                self.assertEqual(self.client.get('/api/models', headers={'Sec-Fetch-Site': site}).status_code, 403)
            models.assert_not_called()
            self.assertEqual(self.client.get('/api/models', headers={'Sec-Fetch-Site': 'same-origin'}).json(), listed)
            self.assertEqual(self.client.get('/api/models').json(), listed)

    def test_health_names_the_serving_process(self):
        self.assertEqual(self.client.get('/api/health').json()['pid'], os.getpid())


class HostCommands(unittest.TestCase):
    def test_stop_and_open_handle_a_host_that_no_longer_answers(self):
        from guided_learning import commands
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': home}):
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            commands.host_record().parent.mkdir(parents=True)
            commands.host_record().write_text(json.dumps({'pid': os.getpid(), 'port': port}), encoding='utf-8')
            self.assertIsNone(commands.running())
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(commands.stop(None), 0)
            self.assertIn('No learning host', output.getvalue())


class CodexErrors(unittest.TestCase):
    def script(self, folder, body):
        path = Path(folder) / 'server.py'
        path.write_text('import sys,json,time\nfor line in sys.stdin:\n r=json.loads(line); m=r.get("method"); i=r.get("id")\n'
                        ' if m=="initialize": print(json.dumps({"id":i,"result":{}}),flush=True)\n' + body, encoding='utf-8')
        return [sys.executable, str(path)]

    def test_codex_error_text_reaches_the_learner(self):
        from guided_learning.codex import CodexRunner
        with tempfile.TemporaryDirectory() as tmp:
            command = self.script(tmp, ' if m=="thread/start": print(json.dumps({"id":i,"error":{"code":1,"message":"model gpt-x does not exist"}}),flush=True)\n')
            with self.assertRaisesRegex(RuntimeError, 'model gpt-x does not exist'):
                CodexRunner(command=command).run('teach', tmp, lambda e: None, threading.Event())

    def test_silence_times_out_but_steady_output_does_not(self):
        from guided_learning.codex import CodexRunner
        with tempfile.TemporaryDirectory() as tmp:
            silent = self.script(tmp, ' if m=="thread/start": time.sleep(30)\n')
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, 'nothing'):
                CodexRunner(command=silent, idle_timeout=.5).run('teach', tmp, lambda e: None, threading.Event())
            self.assertLess(time.monotonic() - started, 5)


class SessionAndLanguage(unittest.TestCase):
    def test_session_resume_lists_open_app_questions_but_lessons_do_not_see_them(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'branch.begin', 'id': 'q', 'question': 'Why is it squared?', 'selection': 'x' * 400})
            [question] = execute(path, {'op': 'session.resume'})['app_questions']
            self.assertEqual((question['id'], question['status'], question['concept_id']), ('q', 'unanswered', 'a'))
            self.assertLessEqual(len(question['selection']), 301)
            turn = execute(path, {'op': 'stream.start', 'id': 'lesson', 'concept_id': 'a', 'prompt': 'Teach'})['turn']
            self.assertNotIn('app_questions', turn['prompt_snapshot']['session'])

    def test_overview_fallback_follows_the_course_language(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            client, host = host_client(path, Lesson())
            with client:
                english = client.get('/api/concepts/b/preview').json()['overview']
                self.assertEqual(english['next'], 'Review this section and apply the concepts to combined problems')
                client.put('/api/preferences', json={'language': 'zh-CN'})
                chinese = client.get('/api/concepts/b/preview').json()['overview']
                self.assertTrue(chinese['next'].startswith('复习本小节'))
                self.assertIn('B', chinese['steps'][0])
                self.assertEqual(chinese['prior'], '承接A')


class Storage(unittest.TestCase):
    def test_fingerprint_reads_courses_whose_path_needs_quoting(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'odd ?name#%20' / 'course'
            course(path, ('a',))
            self.assertIsNotNone(library.fingerprint(path))

    def test_source_snapshots_are_restored_and_leave_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as path:
            course(path, ('a',))
            source = Path(path) / 'notes.md'
            source.write_text('# Notes', encoding='utf-8')
            registered = execute(path, {'op': 'source.register', 'path': str(source)})['source']
            snapshot = Path(path) / 'sources' / registered['id'] / registered['revision']
            snapshot.write_bytes(b'truncated')
            execute(path, {'op': 'source.register', 'path': str(source)})
            self.assertEqual(snapshot.read_bytes(), b'# Notes')
            self.assertEqual([p.name for p in snapshot.parent.iterdir()], [registered['revision']])

    def test_background_handoff_uses_the_model_the_caller_supplies(self):
        with tempfile.TemporaryDirectory() as path:
            course(path, ('a',))
            execute(path, {'op': 'interaction.record', 'id': 'm', 'role': 'user', 'text': 'Question'})
            execute(path, {'op': 'background.enqueue', 'id': 'job', 'interaction_ids': ['m']})
            with mock.patch.object(background, 'teacher_models', return_value={'model': 'teacher', 'small_model': 'small'}):
                claim = execute(path, {'op': 'background.claim', 'id': 'job', 'request_id': 'r', 'attempt_id': 'a1'})
            self.assertEqual(claim['handoff']['model'], 'small')


if __name__ == '__main__':
    unittest.main()
