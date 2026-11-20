"""Updating while a host from before sign-in codes (0.52–0.54.0) still runs: it answers /api/health but turns the
current key away, so `open` and `stop` stop it another way and `open` starts the current version's host."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from guided_learning import commands, library

FAKE = Path(__file__).with_name('fake_old_host.py')
LEGACY = 'c' * 64


class OldHost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        library.state_dir().mkdir(parents=True)

    def start(self, key):
        """The old host, recorded as `open` recorded it; `key` is what it accepts, '' for nothing (its key is lost)."""
        process = subprocess.Popen([sys.executable, str(FAKE), key], stdout=subprocess.PIPE, text=True)
        self.addCleanup(process.stdout.close)
        self.addCleanup(lambda: process.poll() is None and (process.kill(), process.wait()))
        port = int(process.stdout.readline())
        commands.host_record().write_text(json.dumps({'pid': process.pid, 'port': port, 'launch_id': None}), encoding='utf-8')
        return process

    def keep_legacy_key(self):
        (library.state_dir() / 'host-key').write_text(LEGACY, encoding='ascii')

    def open(self):
        started = {'pid': 1, 'port': 8765, 'launch_id': 'new'}
        with mock.patch.object(commands, '_spawn', return_value=started) as spawn, \
                mock.patch.object(commands, 'app_url', return_value='http://127.0.0.1:8765/?code=x'), \
                redirect_stdout(StringIO()):
            code = commands.open_course(argparse.Namespace(course=None, port=8765, no_browser=True))
        return code, spawn

    def test_open_stops_the_old_host_with_the_key_it_kept_and_starts_a_current_one(self):
        self.keep_legacy_key()
        library.host_key()  # this version's key, which the old host turns away
        old = self.start(LEGACY)
        code, spawn = self.open()
        self.assertEqual(code, 0)
        self.assertEqual(old.wait(timeout=10), 0, 'asked to stop, it stopped by itself')
        spawn.assert_called_once_with(8765)
        self.assertFalse((library.state_dir() / 'host-key').exists(), 'the printed key goes once its host has')

    def test_open_ends_an_old_host_whose_key_is_gone(self):
        old = self.start('')  # 0.54.1–0.55.0 deleted host-key while it still ran
        code, spawn = self.open()
        self.assertEqual(code, 0)
        self.assertIsNotNone(old.wait(timeout=10))
        spawn.assert_called_once_with(8765)

    def test_stop_stops_an_old_host(self):
        self.keep_legacy_key()
        old = self.start(LEGACY)
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(commands.stop(argparse.Namespace()), 0)
        self.assertEqual(old.wait(timeout=10), 0)
        self.assertIn('stopped', output.getvalue())

    def test_stop_ends_an_old_host_whose_key_is_gone(self):
        old = self.start('')
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(commands.stop(argparse.Namespace()), 0)
        self.assertIsNotNone(old.wait(timeout=10))

    def test_a_current_host_is_used_as_it_is(self):
        record = {'pid': 2, 'port': 8765, 'launch_id': 'x'}
        with mock.patch.object(commands, 'running', return_value=record), \
                mock.patch.object(commands, '_call', return_value={'code': 'f' * 32}), \
                mock.patch.object(commands, '_stop_other') as stop_other:
            self.assertEqual(commands.current(), record)
        stop_other.assert_not_called()


if __name__ == '__main__':
    unittest.main()
