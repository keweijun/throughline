"""Database and streaming overhead: write-ahead logging, lock-free reads, batched stream writes and an idle watcher."""
import asyncio
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from guided_learning import api
from guided_learning.api import execute
from guided_learning.server import Host
from guided_learning.server import host as host_module
from support import ROOT, call_cli


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})


def journal_mode(path):
    db = sqlite3.connect(Path(path) / 'course.sqlite3')
    try:
        return db.execute('PRAGMA journal_mode').fetchone()[0]
    finally:
        db.close()


class Gate:
    """A runner that streams `deltas` words, waits for `release`, then completes."""

    def __init__(self, deltas=5, pause=0.0):
        self.deltas, self.pause = deltas, pause
        self.streamed, self.release = threading.Event(), threading.Event()

    def run(self, prompt, cwd, emit, cancel):
        for i in range(self.deltas):
            emit({'kind': 'delta', 'text': f'w{i} '})
            if self.pause:
                time.sleep(self.pause)
        self.streamed.set()
        self.release.wait(10)
        if cancel.is_set():
            return
        emit({'kind': 'final', 'text': 'Whole lesson.'})
        emit({'kind': 'complete'})


class Database(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = tmp.name
        course(self.workspace)

    def test_courses_use_write_ahead_logging(self):
        self.assertEqual(journal_mode(self.workspace), 'wal')
        db = sqlite3.connect(Path(self.workspace) / 'course.sqlite3')
        db.execute('PRAGMA journal_mode=DELETE')
        db.close()
        execute(self.workspace, {'op': 'course.status'})
        self.assertEqual(journal_mode(self.workspace), 'wal', 'a course made by an older version switches on its next operation')

    def test_operations_beside_an_open_host_keep_the_log_files(self):
        host = Host(self.workspace)
        self.addCleanup(host.close)
        log = Path(self.workspace) / 'course.sqlite3-wal'
        before = log.stat().st_ino
        for language in ('zh-CN', 'en'):
            execute(self.workspace, {'op': 'preferences.save', 'language': language})
            execute(self.workspace, {'op': 'course.status'})
        self.assertEqual(log.stat().st_ino, before, 'the log is not deleted and created again')

    def test_reads_do_not_wait_for_a_writer(self):
        writer = sqlite3.connect(Path(self.workspace) / 'course.sqlite3', isolation_level=None)
        writer.execute('BEGIN IMMEDIATE')
        writer.execute("UPDATE documents SET value=value WHERE namespace='course'")
        results = []
        reader = threading.Thread(target=lambda: results.extend(execute(self.workspace, {'op': op}) for op in
                                                                ('course.status', 'curriculum.view', 'session.resume', 'stream.summaries')))
        reader.start()
        reader.join(5)
        finished = len(results)
        writer.execute('ROLLBACK')
        writer.close()
        reader.join()
        self.assertEqual(finished, 4, 'reads finished while another connection held the write lock')

    def test_a_read_that_writes_still_commits(self):
        """An operation classified as a read but writing after all is retried under the write lock, not lost."""
        api.READS.add('preferences.save')
        self.addCleanup(api.READS.discard, 'preferences.save')
        execute(self.workspace, {'op': 'preferences.save', 'language': 'zh-CN'})
        self.assertEqual(execute(self.workspace, {'op': 'preferences.view'})['preferences']['language'], 'zh-CN')

    def test_stream_events_applies_a_batch_in_order_once(self):
        execute(self.workspace, {'op': 'stream.start', 'id': 'l', 'concept_id': 'state', 'prompt': 'Explain'})
        batch = {'op': 'stream.events', 'id': 'l', 'attempt': 1,
                 'events': [{'sequence': 1, 'kind': 'delta', 'text': 'a'}, {'sequence': 2, 'kind': 'delta', 'text': 'b'}]}
        self.assertEqual(execute(self.workspace, batch)['turn']['text'], 'ab')
        self.assertTrue(execute(self.workspace, batch)['ignored'], 'a replayed batch changes nothing')
        result = execute(self.workspace, {**batch, 'events': [{'sequence': 2, 'kind': 'delta', 'text': 'b'}, {'sequence': 3, 'kind': 'final', 'text': 'Done.'},
                                                              {'sequence': 4, 'kind': 'complete'}]})
        self.assertEqual((result['turn']['status'], result['turn']['text'], result['turn']['sequence']), ('completed', 'Done.', 4))
        self.assertEqual(execute(self.workspace, {'op': 'interaction.read', 'id': 'stream:l'})['interaction']['text'], 'Done.')


class StreamWrites(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = tmp.name
        course(self.workspace)
        self.writes = []
        real = host_module.execute

        def counting(workspace, request):
            if request['op'] in ('stream.event', 'stream.events'):
                self.writes.append(request)
            return real(workspace, request)
        host_module.execute = counting
        self.addCleanup(setattr, host_module, 'execute', real)

    def host(self, runner, interval):
        host = Host(self.workspace, runner=runner)
        host.persist_interval = interval
        self.addCleanup(host.close)
        return host

    def stored(self, identifier):
        return execute(self.workspace, {'op': 'stream.read', 'id': identifier})['turn']

    def test_a_streamed_lesson_is_written_a_few_times_while_every_delta_is_published_in_order(self):
        runner = Gate(deltas=100, pause=0.002)
        runner.release.set()
        host = self.host(runner, 0.1)
        seen = []

        async def collect():
            subscriber = host.events.subscribe()
            await asyncio.to_thread(host.start_turn, {'id': 'l', 'concept_id': 'state', 'prompt': 'Explain'})
            while True:
                event = await asyncio.wait_for(subscriber[1].get(), 5)
                seen.append(event)
                if event['type'] == 'turn' and event['turn']['status'] == 'completed':
                    return
        asyncio.run(collect())
        deltas = [e for e in seen if e['type'] == 'delta']
        self.assertEqual([e['sequence'] for e in deltas], list(range(1, 101)))
        self.assertEqual(''.join(e['text'] for e in deltas), ''.join(f'w{i} ' for i in range(100)))
        self.assertLess(len(self.writes), 15, f'{len(self.writes)} stream writes for 100 deltas')
        turn = self.stored('l')
        self.assertEqual((turn['status'], turn['text'], turn['sequence']), ('completed', 'Whole lesson.', 102))

    def test_reads_through_the_host_include_every_published_delta(self):
        runner = Gate()
        host = self.host(runner, 60)
        host.start_turn({'id': 'l', 'concept_id': 'state', 'prompt': 'Explain'})
        self.assertTrue(runner.streamed.wait(5))
        expected = ''.join(f'w{i} ' for i in range(5))
        turn = host.operation({'op': 'stream.read', 'id': 'l'})['turn']
        self.assertEqual((turn['text'], turn['sequence']), (expected, 5))
        summary = next(t for t in host.operation({'op': 'stream.summaries'})['turns'] if t['id'] == 'l')
        self.assertEqual(summary['text'], expected)
        runner.release.set()
        self.assertEqual(host.wait('l', 5)['status'], 'completed')

    def test_pausing_keeps_the_text_streamed_so_far(self):
        runner = Gate()
        host = self.host(runner, 60)
        host.start_turn({'id': 'l', 'concept_id': 'state', 'prompt': 'Explain'})
        self.assertTrue(runner.streamed.wait(5))
        host.pause_turn('l')
        runner.release.set()
        turn = host.wait('l', 5)
        self.assertEqual((turn['status'], turn['text']), ('paused', ''.join(f'w{i} ' for i in range(5))))

    def test_a_host_that_dies_mid_stream_leaves_the_text_written_so_far(self):
        runner = Gate()
        host = self.host(runner, 0.05)
        host.start_turn({'id': 'l', 'concept_id': 'state', 'prompt': 'Explain'})
        self.assertTrue(runner.streamed.wait(5))
        expected = ''.join(f'w{i} ' for i in range(5))
        for _ in range(100):
            if self.stored('l')['text'] == expected:
                break
            time.sleep(0.02)
        # The process dies here: nothing more is written, and the next host recovers the turn.
        execute(self.workspace, {'op': 'stream.recover'})
        turn = self.stored('l')
        self.assertEqual((turn['status'], turn['text']), ('interrupted', expected))
        runner.release.set()

    def test_codex_reads_and_writes_the_course_while_a_lesson_streams(self):
        runner = Gate(deltas=400, pause=0.002)
        runner.release.set()
        host = self.host(runner, 0.05)
        host.start_turn({'id': 'l', 'concept_id': 'state', 'prompt': 'Explain'})
        for i in range(3):
            self.assertEqual(call_cli(self, self.workspace, 'course.status')['course']['title'], 'Quantum')
            call_cli(self, self.workspace, 'memory.save', id=f'm{i}', kind='preference', concept_id='state', text=f'Prefers worked examples {i}')
        turn = host.wait('l', 15)
        self.assertEqual((turn['status'], turn['text']), ('completed', 'Whole lesson.'))
        self.assertEqual(len(call_cli(self, self.workspace, 'memory.view')['entries']), 3)
