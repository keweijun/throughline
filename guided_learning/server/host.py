"""The learning host: owns a course workspace and runs every model turn through one engine."""
import asyncio
import logging
import os
import threading
import time
import uuid
from pathlib import Path

from ..api import execute
from ..streaming import PREPARED_STEP, SMALL_MODEL, summarize
from .settings import TeacherSettings
from ..store import OperationError, hold
from . import prompts
from .state import public_turn

log = logging.getLogger(__name__)


class EventBus:
    """Fan-out of host events to SSE subscribers; safe to publish from worker threads."""

    def __init__(self):
        self.lock = threading.Lock()
        self.subscribers = set()

    def subscribe(self):
        subscriber = (asyncio.get_running_loop(), asyncio.Queue(maxsize=2000))
        with self.lock:
            self.subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber):
        with self.lock:
            self.subscribers.discard(subscriber)

    def publish(self, event):
        with self.lock:
            subscribers = list(self.subscribers)
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(_offer, queue, event)
            except RuntimeError:
                self.unsubscribe((loop, queue))


def _offer(queue, event):
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(event)


def _acquire_lease(workspace):
    lease = (workspace / '.learning-host.lock').open('a+b')
    lease.seek(0)
    lease.write(b'0')
    lease.flush()
    lease.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lease.close()
        raise OperationError('host_running', 'Another learning host already owns this course')
    return lease


turn_summary = summarize
# What a finished background turn changes besides itself: the interface reloads only that part of the state.
FINISHED = {'preparation': 'preparation', 'consolidation': 'memory'}


class Host:
    def __init__(self, workspace, runner=None, settings=None, events=None):
        from .features import Memory, Navigation, Practice, Preparation, Questions
        from .builds import ChapterBuilds
        from .review import Review
        self.workspace = Path(workspace).resolve()
        self.settings = settings or TeacherSettings()
        self._runner = runner
        self.events = events or EventBus()
        self.lock = threading.RLock()
        self.closing = False
        self.workers = {}
        # Streamed events are published at once but stored a few times a second (`persist_interval`); every operation
        # through the host stores them first, so what it reads includes every published delta.
        self.persist_interval = 0.25
        self._streams = threading.RLock()
        self._pending = {}  # (turn id, attempt) -> events not yet stored
        self._live = {}  # (turn id, attempt) -> channel, while this host streams the attempt
        self._timer = None
        self.operation({'op': 'course.status'})
        self._lease = _acquire_lease(self.workspace)
        self._held = hold(self.workspace)
        self.operation({'op': 'stream.recover'})
        self.navigation = Navigation(self)
        self.questions = Questions(self)
        self.practice = Practice(self)
        self.preparation = Preparation(self)
        self.builds = ChapterBuilds(self)
        self.review = Review(self)
        self.memory = Memory(self)
        # Order matters: prompt additions are appended, and completions handled, in this order; memory goes last, after
        # practice has recorded the interactions a note cites.
        self.features = (self.navigation, self.questions, self.practice, self.preparation, self.builds, self.memory)
        self.questions.recover()
        self.navigation.recover()
        self.preparation.start()
        self.builds.start()

    @property
    def runner(self):
        return self._runner or self.settings.runner()

    def runner_for(self, turn):
        # Preparation and memory consolidation are background work, so they run on the small model when one is chosen; a
        # chapter build needs the teacher.
        return self._runner or self.settings.runner(small=turn['channel'] in SMALL_MODEL)

    def operation(self, request):
        if self._pending:
            try:
                self._persist()
            except Exception:
                log.exception('Could not store streamed text before %s', request.get('op'))
        return execute(self.workspace, request)

    def _persist(self, key=None):
        """Store buffered stream events, of one attempt or all; returns the last write's result. Events that cannot be
        stored stay buffered for the next try."""
        result = None
        with self._streams:
            for key in [key] if key else list(self._pending):
                events = self._pending.pop(key, None)
                if not events:
                    continue
                try:
                    result = execute(self.workspace, {'op': 'stream.events', 'id': key[0], 'attempt': key[1], 'events': events})
                except Exception:
                    self._pending[key] = events
                    raise
                if result.get('ignored'):
                    self._live.pop(key, None)  # stopped elsewhere; later events of this attempt are dropped
        return result

    def _tick(self):
        with self._streams:
            self._timer = None
            try:
                self._persist()
            except Exception:
                log.exception('Could not store streamed text')

    def changed(self, scope='state'):
        self.events.publish({'type': 'changed', 'scope': scope})
        self._wake_background()

    def _wake_background(self):
        for name in ('preparation', 'builds'):
            feature = getattr(self, name, None)
            if feature:
                feature.wake()

    def turns(self):
        """Every turn in full, with frozen prompt snapshots; prefer `brief_turns` when only status matters."""
        return self.operation({'op': 'stream.list'})['turns']

    def brief_turns(self):
        """Each turn's id, channel, section, attempt and status, without its text or snapshot."""
        return self.operation({'op': 'stream.summaries', 'brief': True})['turns']

    def snapshot(self):
        return {**self.operation({'op': 'course.status'}),
                **self.operation({'op': 'preferences.view'}),
                'curriculum': self.operation({'op': 'curriculum.view'}),
                'session': self.operation({'op': 'session.resume', 'recent_limit': 20}),
                'deferred_explanations': self.operation({'op': 'deferred.list'})['deferred_explanations'],
                # A prepared step stays hidden until Continue reveals it.
                'turns': [t for t in self.operation({'op': 'stream.summaries'})['turns'] if t['channel'] != PREPARED_STEP]}

    def publish_turn(self, turn):
        if turn['channel'] == PREPARED_STEP:
            return
        with self._streams:
            self.events.publish({'type': 'turn', 'turn': public_turn(turn_summary(turn))})
            key = (turn['id'], turn['attempt'])
            if self._live.get(key) == PREPARED_STEP:
                # Revealed while streaming: send what was written after this copy, and stream from here.
                self._live[key] = turn['channel']
                for event in self._pending.get(key, []):
                    if event['kind'] == 'delta' and event['sequence'] > turn['sequence']:
                        self._publish_delta(key, event)

    def _publish_delta(self, key, event):
        self.events.publish({'type': 'delta', 'id': key[0], 'attempt': key[1], 'sequence': event['sequence'], 'text': event.get('text', '')})

    def completed(self, turn):
        """Run every feature's completion hook for a turn stored as completed."""
        for feature in self.features:
            try:
                feature.on_complete(turn)
            except Exception:
                log.exception('%s could not finish turn %s', feature.__class__.__name__, turn['id'])

    def set_language(self, language):
        with self.lock:
            result = self.operation({'op': 'preferences.save', 'language': language})
            stale = {job['id'] for job in self.preparation.state()['jobs'] if job['status'] == 'stale'}
            for turn in self.brief_turns():
                if turn['id'] in stale and turn['status'] == 'running':
                    self.pause_turn(turn['id'])
            self.changed('preferences')
            return result

    def build_prompt(self, turn):
        if turn.get('prompt_snapshot') is None:
            raise OperationError('missing_snapshot', 'This older turn has no source snapshot; start a new lesson')
        if turn['channel'] == 'build':
            return self.builds.build_prompt(turn)  # not a teaching turn: none of the teaching additions apply
        if turn['channel'] == 'consolidation':
            return self.memory.consolidation_prompt(turn)
        prompt = prompts.base(turn)
        context = turn['prompt_snapshot']['context']
        for feature in self.features:
            addition = feature.prompt(turn, context)
            if addition:
                prompt += '\n' + addition
        return prompt

    def ensure_single_mainline(self, identifier, message):
        for other in self.brief_turns():
            if other['id'] != identifier and other['channel'] == 'mainline' and other['status'] == 'running':
                raise OperationError('active_turn', message)

    def start_turn(self, request):
        with self.lock:
            if self.closing:
                raise OperationError('host_closing', 'Learning server is closing')
            request = {**request, 'id': request.get('id') or str(uuid.uuid4())}
            if request.get('channel', 'mainline') == 'mainline':
                self.ensure_single_mainline(request['id'], 'Pause the current lesson before starting another')
            for feature in self.features:
                feature.before_start(request)
            result = self.operation({**request, 'op': 'stream.start'})
            if result['created']:
                self._launch(result['turn'])
            return result

    def start_lesson(self, body):
        """Start a mainline lesson, entering the first route concept when no position exists yet."""
        with self.lock:
            position = self.operation({'op': 'course.status'})['position'] or {}
            if not position.get('concept_id'):
                curriculum = self.operation({'op': 'curriculum.view'})
                if not curriculum['route']:
                    raise OperationError('no_route', 'Plan a course route first')
                first = next(c for c in curriculum['concepts'] if c['id'] == curriculum['route'][0])
                chinese = self.operation({'op': 'preferences.view'})['preferences']['language'] == 'zh-CN'
                self.operation({'op': 'mainline.enter', 'request_id': str(uuid.uuid4()), 'concept_id': first['id'],
                                'goal': prompts.section_goal(first, chinese),
                                'next_step': '阅读讲解，然后尝试练习' if chinese else 'Read the lesson, then try the exercises'})
                position = self.operation({'op': 'course.status'})['position']
            return self.navigation.start_lesson(position['concept_id'], body)

    def _launch(self, turn):
        cancel = threading.Event()
        identifier, attempt = turn['id'], turn['attempt']
        key = (identifier, attempt)
        with self._streams:
            self._live[key] = turn['channel']
        self.publish_turn(turn)

        def emit(event):
            if event['kind'] == 'delta' and cancel.is_set():
                return  # paused: the stored turn ignores it
            with self._streams:
                if key not in self._live:
                    return
                emit.sequence += 1
                self._pending.setdefault(key, []).append({**event, 'sequence': emit.sequence})
                if event['kind'] == 'delta':
                    # A prepared step's text is published once Continue reveals it, and streams from there.
                    if self._live[key] != PREPARED_STEP:
                        self._publish_delta(key, self._pending[key][-1])
                    if self._timer is None:
                        self._timer = threading.Timer(self.persist_interval, self._tick)
                        self._timer.daemon = True
                        self._timer.start()
                    return
                try:
                    result = self._persist(key)
                except Exception:
                    # Earlier events stay buffered; this one is not counted, so the attempt can still be marked failed.
                    self._pending[key].pop()
                    emit.sequence -= 1
                    raise
                if event['kind'] in ('complete', 'failed'):
                    self._live.pop(key, None)
            if result is None or result.get('ignored'):
                return
            if event['kind'] in ('complete', 'failed'):
                self.publish_turn(result['turn'])
                if event['kind'] == 'complete':
                    self.completed(result['turn'])
                self.changed(FINISHED.get(result['turn']['channel'], 'state'))
        emit.sequence = 0

        def fail(message):
            """Mark this attempt failed after whatever is stored, whatever happened to earlier events."""
            with self._streams:
                try:
                    self._persist(key)
                except Exception:
                    log.exception('Could not store the rest of turn %s attempt %s', identifier, attempt)
                    self._pending.pop(key, None)
                current = execute(self.workspace, {'op': 'stream.read', 'id': identifier})['turn']
                if current['attempt'] != attempt or current['status'] != 'running':
                    self._live.pop(key, None)
                    return
                self._live.setdefault(key, current['channel'])
                emit.sequence = current['sequence']
            try:
                emit({'kind': 'failed', 'error': message})
            except Exception:
                with self._streams:
                    self._pending.pop(key, None)
                raise

        def work():
            try:
                prompt = self.build_prompt(turn)
                images = [path for feature in self.features for path in feature.images(turn)]
                # Only a turn with images passes them, so runners without an `images` parameter keep working (ADR 0002).
                self.runner_for(turn).run(prompt, self.workspace, emit, cancel, **({'images': images} if images else {}))
                fail('Model ended without a completed reply')
            except Exception as exc:
                log.info('Turn %s attempt %s failed', identifier, attempt, exc_info=True)
                try:
                    fail(str(exc) or exc.__class__.__name__)
                except Exception:
                    log.exception('Could not mark turn %s attempt %s failed', identifier, attempt)
            finally:
                with self._streams:
                    self._live.pop(key, None)
                if self.workers.get(key, (None,))[0] is threading.current_thread():
                    self.workers.pop(key, None)
                self._wake_background()

        thread = threading.Thread(target=work, daemon=True, name=f'turn-{identifier}')
        self.workers[key] = (thread, cancel)
        thread.start()

    def pause_turn(self, identifier):
        with self.lock:
            result = self.operation({'op': 'stream.pause', 'id': identifier})
            worker = self.workers.get((identifier, result['turn']['attempt']))
            if worker:
                worker[1].set()
            self.publish_turn(result['turn'])
            if result['turn']['channel'] == 'mainline':
                self.navigation.discard_prepared()  # pausing the lesson, for a side question say, stops writing ahead
            self._wake_background()
            return result

    def resume_turn(self, identifier, request_id):
        with self.lock:
            if self.closing:
                raise OperationError('host_closing', 'Learning server is closing')
            previous = self.operation({'op': 'stream.read', 'id': identifier})['turn']
            if previous['channel'] == PREPARED_STEP:
                raise OperationError('invalid_transition', 'A prepared step that stopped is discarded, not regenerated')
            if previous['channel'] == 'mainline':
                self.ensure_single_mainline(identifier, 'Pause the current lesson before resuming another')
            worker = self.workers.get((identifier, previous['attempt']))
            if worker and worker[0].is_alive():
                raise OperationError('stopping', 'The model is still stopping; try again in a moment')
            for feature in self.features:
                feature.before_start(previous)
            result = self.operation({'op': 'stream.resume', 'id': identifier, 'request_id': request_id})
            if result['created']:
                self._launch(result['turn'])
            return result

    def worker_alive(self, turn):
        worker = self.workers.get((turn['id'], turn['attempt']))
        return bool(worker and worker[0].is_alive())

    def wait(self, identifier, timeout=None):
        turn = self.operation({'op': 'stream.read', 'id': identifier})['turn']
        worker = self.workers.get((identifier, turn['attempt']))
        if worker:
            worker[0].join(timeout)
        return self.operation({'op': 'stream.read', 'id': identifier})['turn']

    def close(self):
        with self.lock:
            if self.closing:
                return
            self.closing = True
            self.preparation.stop()
            self.builds.stop()
            workers = list(self.workers.items())
            for (identifier, _), (_, cancel) in workers:
                self.pause_turn(identifier)
                cancel.set()
        # No new workers can start while shutdown waits for the owned model processes.
        deadline = time.monotonic() + 12
        for _, (thread, _) in workers:
            thread.join(max(0, deadline - time.monotonic()))
        self.preparation.join(2)
        self.builds.join(2)
        try:
            self._persist()
        except Exception:
            log.exception('Could not store streamed text while closing')
        self._held.close()
        self._lease.close()
