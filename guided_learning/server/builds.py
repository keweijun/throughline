"""Builds the next outlined chapter in the background (ADR 0004), after the learner's own requests.

The build is a read-only teacher turn whose reply is the chapter as JSON; the host saves it with
`curriculum.chapter.save` (through `chapter_build.complete`) and retries once with the validation error.
"""
import json
import logging
import threading
import uuid
from pathlib import Path

from ..store import OperationError
from . import prompts
from .features import Feature

log = logging.getLogger(__name__)

LEARNER_CHANNELS = ('mainline', 'sidequestion', 'practice')
SOURCE_LIMIT = 60_000  # characters of source text in one build prompt
UNIT_OVERHEAD = 60  # what one unit's JSON framing costs, counted against the limit


class ChapterBuilds(Feature):
    INTERVAL = 2  # seconds between checks when nothing wakes the loop
    START_DELAY = .5

    def __init__(self, host):
        super().__init__(host)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='chapter-builds')

    def start(self):
        self.recover()
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def wake(self):
        self._wake.set()

    def join(self, timeout):
        if self._thread.is_alive():
            self._thread.join(timeout)

    def state(self):
        return self.operation({'op': 'chapter_build.list'})['builds']

    def request(self, chapter_id):
        """The learner asked for a chapter; it starts once their own requests have finished."""
        with self.host.lock:
            result = self.operation({'op': 'chapter_build.request', 'chapter_id': chapter_id, 'trigger': 'learner'})
        self._publish()
        self.wake()
        return {'build': result['build']}

    def _publish(self):
        # Publish directly: host.changed() would wake this loop again.
        self.host.events.publish({'type': 'changed', 'scope': 'builds'})

    def _auto_request(self):
        """Studying the last built chapter asks for the next outlined one, once."""
        concept_id = (self.operation({'op': 'course.status'})['position'] or {}).get('concept_id')
        chapters = self.operation({'op': 'curriculum.view'})['chapters']
        built = [i for i, c in enumerate(chapters) if c['concept_ids']]
        if not concept_id or not built or built[-1] + 1 >= len(chapters) or concept_id not in chapters[built[-1]]['concept_ids']:
            return
        try:
            result = self.operation({'op': 'chapter_build.request', 'chapter_id': chapters[built[-1] + 1]['id'], 'trigger': 'auto'})
        except OperationError:
            return  # another chapter is being built
        if result['created']:
            self._publish()

    def schedule(self):
        with self.host.lock:
            if self.host.closing:
                return {'started': False, 'reason': 'host_closing'}
            self._auto_request()
            queued = next((b for b in self.state() if b['status'] == 'queued'), None)
            if not queued:
                return {'started': False, 'reason': 'nothing_queued'}
            turns = self.host.brief_turns()
            # A paused build can still be shutting down; never run two builds.
            if any(t['channel'] == 'build' and (t['status'] == 'running' or self.host.worker_alive(t)) for t in turns):
                return {'started': False, 'reason': 'building'}
            if any(t['channel'] in LEARNER_CHANNELS and t['status'] == 'running' for t in turns):
                return {'started': False, 'reason': 'learner_active'}
            turn_id = 'build-' + str(uuid.uuid4())
            self.operation({'op': 'chapter_build.begin', 'chapter_id': queued['chapter_id'], 'turn_id': turn_id})
            try:
                result = self.host.start_turn({'id': turn_id, 'concept_id': self._anchor(queued['chapter_id']), 'channel': 'build',
                                               'record_user': False, 'prompt': prompts.BUILD_REQUEST})
            finally:
                # A turn that could not start leaves the build interrupted, for the learner to retry.
                self._publish()
            return {'started': True, 'turn': result['turn']}

    def _anchor(self, chapter_id):
        """Every turn belongs to a route section: the last one before the chapter being built."""
        model = self.operation({'op': 'curriculum.view'})
        before = []
        for chapter in model['chapters']:
            if chapter['id'] == chapter_id:
                break
            before += chapter['concept_ids']
        return (before or model['route'])[-1]

    def _record(self, turn):
        return next((b for b in self.state() if b.get('turn_id') == turn['id']), None)

    def build_prompt(self, turn):
        record = self._record(turn)
        if record is None:
            raise OperationError('stale_build', 'This chapter build is no longer current')
        data, truncated = self._data(record['chapter_id'], turn['prompt_snapshot'])
        return prompts.chapter_build(data, turn.get('language', 'en'), truncated, record.get('retry'))

    def _data(self, chapter_id, snapshot):
        model = self.operation({'op': 'curriculum.view'})
        status = self.operation({'op': 'course.status'})
        chapters = model['chapters']
        index = next(i for i, c in enumerate(chapters) if c['id'] == chapter_id)
        concepts = {c['id']: c for c in model['concepts']}

        def brief(chapter):
            return {k: chapter[k] for k in ('id', 'title', 'summary') if chapter.get(k)}
        data = {'course': (status['course'] or {}).get('title'), 'target': brief(chapters[index]),
                'outline': [{**brief(c), 'built': bool(c['concept_ids'])} for c in chapters],
                'built_route': [{'chapter_id': c['id'], 'title': c['title'],
                                 'sections': [{k: concepts[cid][k] for k in ('id', 'title', 'prerequisites') if k in concepts[cid]} for cid in c['concept_ids']]}
                                for c in chapters if c['concept_ids']]}
        if snapshot.get('learner_profile'):
            data['learner_profile'] = snapshot['learner_profile']
        previous = next((c for c in reversed(chapters[:index]) if c['concept_ids']), None)
        data['source_units'], truncated = self._units(status['sources'], set(previous['concept_ids']) if previous else set())
        return data, truncated

    def _units(self, sources, previous_ids):
        """Unmapped units first, then set-aside ones as context, within the limit, starting after the previous chapter's material."""
        every = self.operation({'op': 'curriculum.coverage'})['units']
        texts = {}
        for source in sources:
            if source.get('revision'):
                try:
                    snapshot = self.operation({'op': 'source.read', 'source_id': source['id'], 'revision': source['revision']})
                except OperationError:
                    continue
                for unit in snapshot['units']:
                    texts[(source['id'], unit['id'])] = unit.get('text') or ''
        order = {(u['source_id'], u['unit_id']): i for i, u in enumerate(every)}
        anchor = max((order[(u['source_id'], u['unit_id'])] for u in every
                      if u['disposition'] == 'mapped' and previous_ids & set(u['concept_ids'])), default=-1)
        # Blank units (empty Markdown lines, pages without extracted text) give the builder nothing to place.
        units = [u for u in every if u['disposition'] != 'mapped' and texts.get((u['source_id'], u['unit_id']), '').strip()]
        rotated = sorted(units, key=lambda u: (order[(u['source_id'], u['unit_id'])] <= anchor, order[(u['source_id'], u['unit_id'])]))
        chosen, used, truncated = [], 0, False
        for wanted in (('unmapped',), ('deferred', 'needs_review')):
            for unit in rotated:
                if unit['disposition'] not in wanted:
                    continue
                cost = len(texts[(unit['source_id'], unit['unit_id'])]) + UNIT_OVERHEAD
                if used + cost > SOURCE_LIMIT:
                    truncated = True
                    continue
                used += cost
                chosen.append(unit)
        chosen.sort(key=lambda u: order[(u['source_id'], u['unit_id'])])
        names = {s['id']: Path(s['path']).name for s in sources}
        grouped = []
        for unit in chosen:
            if not grouped or (grouped[-1]['source_id'], grouped[-1]['revision']) != (unit['source_id'], unit['revision']):
                grouped.append({'source_id': unit['source_id'], 'revision': unit['revision'], 'title': names.get(unit['source_id']), 'units': []})
            entry = {'unit_id': unit['unit_id'], 'disposition': unit['disposition'], 'text': texts[(unit['source_id'], unit['unit_id'])]}
            if unit.get('reason'):
                entry['reason'] = unit['reason']
            grouped[-1]['units'].append(entry)
        return grouped, truncated

    def on_complete(self, turn):
        if turn['channel'] != 'build':
            return
        record = self._record(turn)
        if record is None or record['status'] != 'building':
            return
        reply = turn.get('final_text') or ''
        request = {'chapter_id': record['chapter_id'], 'turn_id': turn['id']}
        try:
            try:
                self.operation({**request, **self.parse(reply), 'op': 'chapter_build.complete'})
            except OperationError as exc:
                if exc.code == 'stale_build':
                    return
                self.operation({**request, 'op': 'chapter_build.reject', 'error': str(exc), 'reply': reply})
        finally:
            self._publish()
            self.wake()

    def parse(self, text):
        """The reply as a chapter.save request; anything malformed is an OperationError the retry can quote."""
        raw = text.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
        try:
            reply = json.loads(raw)
        except ValueError as exc:
            raise OperationError('invalid_build', f'The reply is not valid JSON: {exc}') from exc
        if not isinstance(reply, dict) or not isinstance(reply.get('concepts'), list) or not reply['concepts']:
            raise OperationError('invalid_build', 'The reply must be a JSON object with a nonempty concepts array')
        coverage = reply.get('coverage', [])
        if not isinstance(coverage, list) or any(not isinstance(e, dict) for e in coverage) or any(not isinstance(c, dict) for c in reply['concepts']):
            raise OperationError('invalid_build', 'concepts and coverage must be arrays of objects')
        existing = {c['id'] for c in self.operation({'op': 'curriculum.view'})['concepts']}
        for concept in reply['concepts']:
            if concept.get('id') in existing:
                # chapter.save would move it here from its own chapter.
                raise OperationError('invalid_build', f'Concept id {concept["id"]} already exists in the course; give every new section a new id')
            for field in ('core_question', 'objective'):
                if not isinstance(concept.get(field), str) or not concept[field].strip():
                    raise OperationError('invalid_build', f'Concept {concept.get("id")} needs a {field}')
        # Only a review of the original pages verifies a location, and nobody reviewed these.
        coverage = [{**{k: v for k, v in e.items() if k != 'verification_note'}, 'verification': 'pending'} for e in coverage]
        result = {'concepts': reply['concepts'], 'coverage': coverage}
        if isinstance(reply.get('summary'), str):
            result['summary'] = reply['summary']
        return result

    def recover(self):
        """Finish a build whose reply was saved just before a crash, without a model call."""
        for record in self.state():
            if record['status'] == 'building':
                try:
                    turn = self.operation({'op': 'stream.read', 'id': record['turn_id']})['turn']
                except OperationError:
                    continue
                if turn['status'] == 'completed':
                    self.on_complete(turn)

    def _loop(self):
        self._stop.wait(self.START_DELAY)
        self._wake.set()
        while not self._stop.is_set():
            self._wake.wait(self.INTERVAL)
            self._wake.clear()
            if self._stop.is_set() or self.host.closing:
                return
            try:
                self.schedule()
            except OperationError:
                log.info('Chapter build could not start', exc_info=True)
            except Exception:
                if self.host.closing:
                    return
                log.exception('Chapter build scheduling failed; retrying')
