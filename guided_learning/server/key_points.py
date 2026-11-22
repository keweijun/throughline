"""Key points in the app (ADR 0024). A lesson writes its section's points as it ends: the last step in its <lesson-step>
block, a single-reply lesson in a <key-points> block. While the host is idle, a background turn writes the points of a
section studied before key points existed, and another the paragraph that opens a chapter's sheet."""
import hashlib
import logging
import re
import uuid

from .. import key_points
from ..store import OperationError
from ..streaming import BACKGROUND, PREPARED_STEP
from . import prompts
from .features import STEP_BLOCK, STEP_REPLY, Feature, chapter_owned, is_recap, tagged_json

log = logging.getLogger(__name__)

POINTS_BLOCK = re.compile(r'<key-points>\s*(\{.*?\})\s*</key-points>', re.S)
SHEET_BLOCK = re.compile(r'<chapter-sheet>\s*(\{.*?\})\s*</chapter-sheet>', re.S)
JOBS = ('key_points', 'chapter_sheet')
# What a lesson turn's text carries besides teaching, left out of the lessons a backfill reads.
NOTES = re.compile(r'\s*<(course-memory|course-change|key-points|teaching-decision)>.*?(</\1>|$)', re.S)


def _digest(values):
    return hashlib.sha1('|'.join(values).encode()).hexdigest()[:12]


class KeyPoints(Feature):
    def __init__(self, host):
        super().__init__(host)
        self.ahead = True  # write missing points when idle; tests that count requests turn it off

    def _current(self, concept_id):
        return self.operation({'op': 'key_points.view', 'concept_id': concept_id})['key_points']

    @staticmethod
    def _for_prompt(current):
        """A section's points as the teacher rewrites them: what they say, not where they link."""
        if not current:
            return None, None
        points = [{k: p[k] for k in key_points.FIELDS if k in p} for p in current['points']]
        return points, [r['text'] for r in current.get('requests', [])] or None

    def _lesson_turn(self, turn):
        return turn['channel'] in ('mainline', PREPARED_STEP) and not is_recap(turn) and not chapter_owned(turn)

    def prompt(self, turn, context):
        if not self._lesson_turn(turn):
            return ''
        current, asked = self._for_prompt(self._current(turn['concept_id']))
        ahead = (turn.get('prompt_snapshot') or {}).get('lesson_step')
        lesson = ahead or self.host.navigation.step_of(turn['id'])[0]
        if lesson:
            return prompts.key_points_step(key_points.MAX_POINTS, current, asked)
        return prompts.key_points_reply(key_points.MAX_POINTS, current, asked)

    def before_start(self, request):
        # The learner's own requests go first; a paused job is resumed when the host is idle again.
        if request.get('channel', 'mainline') in BACKGROUND:
            return
        for turn in self.host.brief_turns():
            if turn['channel'] in JOBS and turn['status'] == 'running':
                self.host.pause_turn(turn['id'])

    def _points(self, concept_id, raw, current, turn_of):
        """The teacher's points as key_points.save takes them. `turn_of(point)` names the lesson turn that taught a
        point; a point "kept" from the current ones keeps its links. Citations of locations the section does not link to
        are dropped rather than refusing the points."""
        if not isinstance(raw, list):
            return None
        refs = {(r['source_id'], r['unit_id']): r for r in self._section_refs(concept_id)}
        kept = (current or {}).get('points', [])
        points = []
        for item in raw:
            if not isinstance(item, dict):
                points.append(item)  # refused as a whole by key_points.save
                continue
            index = item.get('kept')
            if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(kept):
                points.append(kept[index])
                continue
            point = {k: item[k] for k in key_points.FIELDS if k in item}
            taught = turn_of(item)
            if taught:
                point['turn_id'] = taught
            cited = item.get('sources') if isinstance(item.get('sources'), list) else []
            point['source_refs'] = [refs[key] for key in dict.fromkeys((s.get('source_id'), s.get('unit_id')) for s in cited if isinstance(s, dict)) if key in refs]
            points.append(point)
        return points

    def _section_refs(self, concept_id):
        concept = next((c for c in self.operation({'op': 'curriculum.view'})['concepts'] if c['id'] == concept_id), {})
        found = []
        for field in ('links', 'exercises', 'notations'):
            for ref in concept.get(field, []):
                exact = {k: ref[k] for k in key_points.REF}
                if exact not in found:
                    found.append(exact)
        return found

    def _save(self, concept_id, turn_id, origin, points):
        if points is None:
            return None
        try:
            return self.operation({'op': 'key_points.save', 'concept_id': concept_id, 'turn_id': turn_id, 'origin': origin, 'points': points})
        except OperationError as exc:
            log.info('Key points from turn %s were refused: %s', turn_id, exc)
            return None

    def on_complete(self, turn):
        if turn['channel'] == 'key_points':
            return self._finish_backfill(turn)
        if turn['channel'] == 'chapter_sheet':
            return self._finish_sheet(turn)
        if turn['channel'] != 'mainline' or is_recap(turn) or chapter_owned(turn):
            return None
        concept_id = turn['concept_id']
        current = self._current(concept_id)
        lesson, _ = self.host.navigation.step_of(turn['id'])
        if lesson:
            if self.host.navigation.steps_remain(turn):
                return None
            reply = tagged_json(STEP_REPLY, turn['final_text']) or {}
            turns = [s.get('turn_id') for s in lesson['steps']]

            def step_turn(item):
                step = item.get('step')
                ok = isinstance(step, int) and not isinstance(step, bool) and 1 <= step <= len(turns)
                return turns[step - 1] if ok else turn['id']
            return self._save(concept_id, turn['id'], 'lesson', self._points(concept_id, reply.get('key_points'), current, step_turn))
        reply = tagged_json(POINTS_BLOCK, turn['final_text']) or {}
        return self._save(concept_id, turn['id'], 'lesson', self._points(concept_id, reply.get('points'), current, lambda item: turn['id']))

    # Idle work: sections studied before key points, then chapter sheets.

    def _current_turns(self, concept_id, turns=None):
        """The completed turns of the section's current lesson, oldest first: a lesson a New lesson replaced (ADR 0023), and
        the replies before it, are history, not what the points sum up."""
        lessons = self.operation({'op': 'lesson.list', 'concept_id': concept_id})['lessons']
        replaced = {s.get('turn_id') for l in lessons if l.get('replaced_by') for s in l['steps']}
        current = [l for l in lessons if not l.get('replaced_by')]
        since = max((l['created_at'] for l in current), default=0) if any(l.get('replaced_by') for l in lessons) else 0
        stepped = {s.get('turn_id') for l in current for s in l['steps']}
        turns = turns if turns is not None else self.host.brief_turns()
        found = [t for t in turns if t['channel'] == 'mainline' and t['status'] == 'completed' and t['concept_id'] == concept_id
                 and not chapter_owned(t) and t['id'] not in replaced and (t['id'] in stepped or t['started_at'] >= since)]
        return sorted(found, key=lambda t: t['started_at'])

    def _lessons_taught(self, concept_id):
        """The section's current lesson, as (turn id, text without its notes or step block) for each of its turns."""
        taught = []
        for brief in self._current_turns(concept_id):
            text = self.operation({'op': 'stream.read', 'id': brief['id']})['turn']['final_text'] or ''
            taught.append((brief['id'], NOTES.sub('', STEP_BLOCK.sub('', text)).strip()))
        return taught

    def _job_id(self, kind, owner, basis):
        return f'{kind}:{owner}:{_digest(basis)}'

    def _start(self, identifier, concept_id, channel, prompt, extra=None):
        """Start, resume or skip a job: a paused or interrupted one resumes, and a failed or finished one is not tried again
        for the same lessons or points, so a failing teacher is never retried in a loop."""
        existing = next((t for t in self.host.brief_turns() if t['id'] == identifier), None)
        if existing:
            if existing['status'] in ('paused', 'interrupted'):
                return self.host.resume_turn(identifier, str(uuid.uuid4()))
            return None if existing['status'] == 'running' else False
        return self.host.start_turn({'id': identifier, 'concept_id': concept_id, 'channel': channel, 'record_user': False,
                                     'prompt': prompt, **(extra or {})})

    def idle(self):
        """Write one missing section's points, or one chapter sheet, when nothing else runs. The current section is left
        out while its lesson still has steps to teach: its last step writes them."""
        with self.host.lock:
            turns = self.host.brief_turns()
            if self.host.closing or any(t['status'] == 'running' and t['channel'] != 'build' for t in turns):
                return None
            position = self.operation({'op': 'course.status'})['position'] or {}
            current = position.get('concept_id')
            exclude = [current] if current and self._teaching(current) else []
            pending = self.operation({'op': 'key_points.pending', 'exclude': exclude})
            for concept_id in pending['sections']:
                taught = [t['id'] for t in self._current_turns(concept_id, turns)]
                started = self._start(self._job_id('key-points', concept_id, sorted(taught)), concept_id, 'key_points', prompts.KEY_POINTS_REQUEST)
                if started is not False:
                    return started
            chapters = {c['id']: c for c in self.operation({'op': 'curriculum.view'})['chapters']}
            for chapter in pending['chapters']:
                basis = self._sheet_basis(chapter)
                # Like any chapter-owned turn, anchored to the chapter's last section (ADR 0006).
                anchor = chapters[chapter['chapter_id']]['concept_ids'][-1]
                started = self._start(self._job_id('chapter-sheet', chapter['chapter_id'], basis), anchor, 'chapter_sheet',
                                      prompts.CHAPTER_SHEET_REQUEST, {'chapter_id': chapter['chapter_id']})
                if started is not False:
                    return started
            return None

    @staticmethod
    def _sheet_basis(chapter):
        return [f'{cid}={at}' for cid, at in sorted(chapter['basis'].items())]

    def _teaching(self, concept_id):
        """Whether the section's current stepped lesson still has steps to teach; a replaced one never goes on."""
        for lesson in self.operation({'op': 'lesson.list', 'concept_id': concept_id})['lessons']:
            if not lesson.get('replaced_by') and any(not s.get('turn_id') for s in lesson['steps']):
                return True
        return False

    def job_prompt(self, turn):
        if turn['channel'] == 'key_points':
            concept = next(c for c in self.operation({'op': 'curriculum.view'})['concepts'] if c['id'] == turn['concept_id'])
            taught = [{'lesson': i + 1, 'text': text} for i, (_, text) in enumerate(self._lessons_taught(turn['concept_id']))]
            _, asked = self._for_prompt(self._current(turn['concept_id']))
            text = prompts.key_points_backfill(concept['title'], taught, key_points.MAX_POINTS, asked)
        else:
            text = prompts.chapter_sheet(*self._sheet_data(turn['chapter_id']))
        return prompts.Prompt(prompts.instructions(turn), prompts.base(turn) + '\n' + text)

    def _sheet_data(self, chapter_id):
        model = self.operation({'op': 'curriculum.view'})
        chapter = next(c for c in model['chapters'] if c['id'] == chapter_id)
        titles = {c['id']: c['title'] for c in model['concepts']}
        found = {v['concept_id']: v for v in self.operation({'op': 'key_points.view'})['key_points']}
        sections = [{'section': titles.get(cid, cid), 'key_points': [p['statement'] for p in found[cid]['points']]}
                    for cid in chapter['concept_ids'] if cid in found]
        return chapter, sections

    def _finish_backfill(self, turn):
        reply = tagged_json(POINTS_BLOCK, turn['final_text']) or {}
        taught = [identifier for identifier, _ in self._lessons_taught(turn['concept_id'])]

        def lesson_turn(item):
            number = item.get('lesson')
            ok = isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= len(taught)
            return taught[number - 1] if ok else None
        current = self._current(turn['concept_id'])
        return self._save(turn['concept_id'], turn['id'], 'backfill', self._points(turn['concept_id'], reply.get('points'), current, lesson_turn))

    def _finish_sheet(self, turn):
        reply = tagged_json(SHEET_BLOCK, turn['final_text']) or {}
        chapter = next((c for c in self.operation({'op': 'key_points.pending'})['chapters'] if c['chapter_id'] == turn.get('chapter_id')), None)
        if not chapter or not isinstance(reply.get('connection'), str):
            return None
        # The paragraph was written from the points the job started with (its id); if they changed since, it is dropped,
        # and the next idle job writes it from the new ones.
        if turn['id'] != self._job_id('chapter-sheet', chapter['chapter_id'], self._sheet_basis(chapter)):
            log.info('Chapter sheet from turn %s was written from points that have changed since', turn['id'])
            return None
        try:
            return self.operation({'op': 'key_points.save_sheet', 'chapter_id': chapter['chapter_id'], 'basis': chapter['basis'],
                                   'connection': reply['connection'], 'turn_id': turn['id']})
        except OperationError as exc:
            log.info('Chapter sheet from turn %s was refused: %s', turn['id'], exc)
            return None

