"""The host log, what Codex writes to stderr when it fails, and the advice a failed turn gives."""
import logging
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from guided_learning import commands, logs
from guided_learning.codex import NOT_FOUND, CodexRunner, list_models

FAILING = '''import sys, json
sys.stderr.write("codex: error loading config.toml: invalid key\\n")
sys.stderr.flush()
for line in sys.stdin:
    r = json.loads(line)
    if r.get('method') == 'initialize':
        print(json.dumps({'id': r['id'], 'result': {}}), flush=True)
    if r.get('method') == 'thread/start':
        print(json.dumps({'id': r['id'], 'result': {'thread': {'id': 't'}}}), flush=True)
    if r.get('method') == 'turn/start':
        print(json.dumps({'id': r['id'], 'result': {'turn': {'id': 'u'}}}), flush=True)
        error = {'message': 'You have hit your usage limit.', 'codexErrorInfo': INFO}
        print(json.dumps({'method': 'turn/completed', 'params': {'threadId': 't', 'turn': {'id': 'u', 'status': 'failed', 'error': error}}}), flush=True)
'''


class HostLog(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = logging.getLogger()
        self.level = self.root.level
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for handler in [h for h in self.root.handlers if getattr(h, 'throughline', False)]:
            self.root.removeHandler(handler)
            handler.close()
        self.root.setLevel(self.level)

    def test_records_go_to_a_rotating_log_once_however_often_it_is_configured(self):
        path = self.tmp / 'state' / 'host.log'
        logs.configure(path)
        handler = logs.configure(path)
        self.assertEqual([h for h in self.root.handlers if getattr(h, 'throughline', False)], [handler])
        self.assertEqual((handler.maxBytes, handler.backupCount), (logs.MAX_BYTES, logs.BACKUPS))
        logging.getLogger('guided_learning.test').warning('Something to look at')
        handler.flush()
        self.assertIn('WARNING guided_learning.test: Something to look at', path.read_text(encoding='utf-8'))

    def test_a_failed_teaching_turn_logs_what_codex_wrote_and_says_what_to_do(self):
        logs.configure(self.tmp / 'host.log')
        for info, advice in [('"usageLimitExceeded"', 'Your Codex usage limit is reached'),
                             ('"unauthorized"', 'Codex is not signed in'),
                             ('{"httpConnectionFailed": {"httpStatusCode": None}}', 'could not reach OpenAI'),
                             ('None', 'Model turn did not complete successfully')]:
            script = self.tmp / 'server.py'
            script.write_text(FAILING.replace('INFO', info), encoding='utf-8')
            with self.assertRaises(RuntimeError) as failed:
                CodexRunner(command=[sys.executable, str(script)]).run('teach', self.tmp, lambda e: None, threading.Event())
            self.assertIn(advice, str(failed.exception))
            self.assertIn('You have hit your usage limit.', str(failed.exception))  # what Codex said stays
        for handler in self.root.handlers:
            handler.flush()
        written = (self.tmp / 'host.log').read_text(encoding='utf-8')
        self.assertIn('A teaching turn failed', written)
        self.assertIn('codex: error loading config.toml: invalid key', written)

    def test_a_connection_lost_without_a_reason_says_the_last_thing_codex_wrote(self):
        script = self.tmp / 'server.py'
        script.write_text('import sys\nsys.stderr.write("Error: not logged in\\n")\nsys.exit(1)\n', encoding='utf-8')
        with self.assertRaises(RuntimeError) as failed:
            CodexRunner(command=[sys.executable, str(script)]).run('teach', self.tmp, lambda e: None, threading.Event())
        self.assertEqual(str(failed.exception), 'Model connection closed before completion: Error: not logged in')

    def test_a_missing_codex_says_how_to_install_it(self):
        missing = [str(self.tmp / 'no-codex-here')]
        with self.assertRaises(RuntimeError) as failed:
            CodexRunner(command=missing).run('teach', self.tmp, lambda e: None, threading.Event())
        self.assertEqual(str(failed.exception), NOT_FOUND)
        with self.assertRaises(RuntimeError) as failed:
            list_models(command=missing)
        self.assertEqual(str(failed.exception), NOT_FOUND)


class Doctor(unittest.TestCase):
    def test_doctor_names_the_system_python_and_host_log(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': tmp}), \
                mock.patch('guided_learning.checks.codex_checks', return_value=[]), \
                mock.patch('guided_learning.checks.codex_answers', return_value={'ok': True, 'label': 'Codex answers', 'model': 'm', 'seconds': 1, 'fix': ''}), \
                mock.patch('guided_learning.checks.probe_model', return_value=None), \
                mock.patch('sys.stdout', new_callable=lambda: __import__('io').StringIO()) as out:
            commands.doctor(None)
        printed = out.getvalue()
        self.assertIn(f'Python {sys.version.split()[0]}', printed)
        self.assertIn(f'Host log: {Path(tmp) / ".throughline" / "host.log"}', printed)


if __name__ == '__main__':
    unittest.main()
