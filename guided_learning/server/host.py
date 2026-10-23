"""The learning host: owns a course workspace and runs every model turn through one engine."""
import asyncio
import os
import threading
import time
import uuid
from pathlib import Path

from ..api import execute
from .settings import TeacherSettings
from ..store import OperationError
from . import prompts


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


def turn_summary(turn):
    """A turn without its frozen prompt snapshot, which the browser never needs."""
    summary = {k: v for k, v in turn.items() if k not in ('prompt_snapshot', 'resume_requests')}
    summary['attempts'] = [{'attempt': a.get('attempt'), 'text': a.get('text'), 'status': a.get('status')} for a in turn.get('attempts', [])]
    concept = (turn.get('prompt_snapshot') or {}).get('context', {}).get('concept') or {}
    summary['title'] = concept.get('title')
    return summary


class Host:
    def __init__(self, workspace, runner=None, settings=None, events=None):
        from .features import Navigation, Practice, Preparation, Questions
        self.workspace = Path(workspace).resolve()
        self.settings = settings or TeacherSettings()
        self._runner = runner
        self.events = events or EventBus()
        self.lock = threading.RLock()
        self.closing = False
        self.workers = {}
        self.operation({'op': 'course.status'})
        self._lease = _acquire_lease(self.workspace)
        self.operation({'op': 'stream.recover'})
        self.navigation = Navigation(self)
        self.questions = Questions(self)
        self.practice = Practice(self)
        self.preparation = Preparation(self)
        # Order matters: prompt additions are appended in this order.
        self.features = (self.navigation, self.questions, self.practice, self.preparation)
        self.questions.recover()
        self.preparation.start()

    @property
    def runner(self):
        return self._runner or self.settings.runner()

    def operation(self, request):
        return execute(self.workspace, request)

    def changed(self, scope='state'):
        self.events.publish({'type': 'changed', 'scope': scope})

    def turns(self):
        return self.operation({'op': 'stream.list'})['turns']

    def snapshot(self):
        return {**self.operation({'op': 'course.status'}),
                **self.operation({'op': 'preferences.view'}),
                'curriculum': self.operation({'op': 'curriculum.view'}),
                'session': self.operation({'op': 'session.resume', 'recent_limit': 20}),
                'deferred_explanations': self.operation({'op': 'deferred.list'})['deferred_explanations'],
                'turns': self.turns()}

    def set_language(self, language):
        with self.lock:
            result = self.operation({'op': 'preferences.save', 'language': language})
            stale = {job['id'] for job in self.preparation.state()['jobs'] if job['status'] == 'stale'}
            for turn in self.turns():
                if turn['id'] in stale and turn['status'] == 'running':
                    self.pause_turn(turn['id'])
            self.changed('preferences')
            return result

    def build_prompt(self, turn):
        if turn.get('prompt_snapshot') is None:
            raise OperationError('missing_snapshot', 'This older turn has no source snapshot; start a new lesson')
        prompt = prompts.base(turn)
        context = turn['prompt_snapshot']['context']
        for feature in self.features:
            addition = feature.prompt(turn, context)
            if addition:
                prompt += '\n' + addition
        return prompt

    def _ensure_single_mainline(self, identifier, message):
        for other in self.turns():
            if other['id'] != identifier and other['channel'] == 'mainline' and other['status'] == 'running':
                raise OperationError('active_turn', message)

    def start_turn(self, request):
        with self.lock:
            if self.closing:
                raise OperationError('host_closing', 'Learning server is closing')
            request = {**request, 'id': request.get('id') or str(uuid.uuid4())}
            if request.get('channel', 'mainline') == 'mainline':
                self._ensure_single_mainline(request['id'], 'Pause the current lesson before starting another')
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
            prompt = (body.get('prompt') or '').strip() or prompts.DEFAULT_LESSON_REQUEST
            return self.start_turn({'id': body.get('id'), 'concept_id': position['concept_id'], 'prompt': prompt, 'channel': 'mainline'})

    def _launch(self, turn):
        cancel = threading.Event()
        identifier, attempt = turn['id'], turn['attempt']
        self.events.publish({'type': 'turn', 'turn': turn_summary(turn)})

        def emit(event):
            emit.sequence += 1
            result = self.operation({'op': 'stream.event', 'id': identifier, 'attempt': attempt, 'sequence': emit.sequence, **event})
            if result.get('ignored'):
                return
            if event['kind'] == 'delta':
                self.events.publish({'type': 'delta', 'id': identifier, 'attempt': attempt, 'text': event.get('text', '')})
            elif event['kind'] in ('complete', 'failed'):
                self.events.publish({'type': 'turn', 'turn': turn_summary(result['turn'])})
                if event['kind'] == 'complete':
                    for feature in self.features:
                        feature.on_complete(result['turn'])
                self.changed()
        emit.sequence = 0

        def work():
            try:
                images = [image for feature in self.features for image in feature.images(turn)]
                arguments = (self.build_prompt(turn), self.workspace, emit, cancel)
                if images:
                    self.runner.run(*arguments, images=images)
                else:
                    self.runner.run(*arguments)
                current = self.operation({'op': 'stream.read', 'id': identifier})['turn']
                if current['attempt'] == attempt and current['status'] == 'running':
                    emit({'kind': 'failed', 'error': 'Model ended without a completed reply'})
            except Exception as exc:
                try:
                    emit({'kind': 'failed', 'error': str(exc) or exc.__class__.__name__})
                except Exception:
                    pass

        thread = threading.Thread(target=work, daemon=True, name=f'turn-{identifier}')
        self.workers[(identifier, attempt)] = (thread, cancel)
        thread.start()

    def pause_turn(self, identifier):
        with self.lock:
            result = self.operation({'op': 'stream.pause', 'id': identifier})
            worker = self.workers.get((identifier, result['turn']['attempt']))
            if worker:
                worker[1].set()
            self.events.publish({'type': 'turn', 'turn': turn_summary(result['turn'])})
            return result

    def resume_turn(self, identifier, request_id):
        with self.lock:
            if self.closing:
                raise OperationError('host_closing', 'Learning server is closing')
            previous = self.operation({'op': 'stream.read', 'id': identifier})['turn']
            if previous['channel'] == 'mainline':
                self._ensure_single_mainline(identifier, 'Pause the current lesson before resuming another')
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
            workers = list(self.workers.items())
            for (identifier, _), (_, cancel) in workers:
                self.pause_turn(identifier)
                cancel.set()
        # No new workers can start while shutdown waits for the owned model processes.
        deadline = time.monotonic() + 12
        for _, (thread, _) in workers:
            thread.join(max(0, deadline - time.monotonic()))
        self.preparation.join(2)
        self._lease.close()
