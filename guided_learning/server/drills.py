"""Drill sessions in the app (ADR 0025): each turn runs on the small model with the scope's key points, mistakes and
review context, and its <drill-questions> block becomes review questions the learner answers in the session. Written
answers to them are assessed on the small model too."""
import logging
import re
import uuid

from ..store import OperationError
from . import prompts
from .features import Feature, tagged_json

log = logging.getLogger(__name__)

QUESTIONS = re.compile(r'<drill-questions>\s*(\{.*?\})\s*</drill-questions>', re.S)
BLOCK = re.compile(r'\s*<drill-questions>.*?(</drill-questions>|$)', re.S)
CONVERSATION = 12  # earlier turns a prompt carries; a session can go on without its prompt growing for ever
OPEN_MISTAKES = 12


class Drills(Feature):
    def state(self):
        return self.operation({'op': 'drill.list'})['sessions']

    def _session(self, identifier):
        found = next((s for s in self.state() if s['id'] == identifier), None)
        if found is None:
            raise OperationError('unknown_session', identifier)
        return found

    def start(self, body):
        """A new session, and its first turn: the learner's message, else "Drill me"."""
        with self.host.lock:
            request = {'id': body.get('id') or 'drill-' + str(uuid.uuid4()), 'kind': body.get('kind') or 'drill'}
            for key in ('scope', 'chapter_id', 'concept_id'):
                if body.get(key):
                    request[key] = body[key]
            session = self.operation({'op': 'drill.create', **request})['session']
            if session['turn_ids']:
                return {'session': self._session(session['id'])}
            return self.send(session['id'], body.get('message'), body.get('turn_id'))

    def send(self, session_id, message=None, turn_id=None):
        """The learner's next message, or More questions (none). One turn of a session runs at a time."""
        with self.host.lock:
            session = self._session(session_id)
            if turn_id and turn_id in session['turn_ids']:
                return {'session': session}
            turns = {t['id']: t for t in self.host.brief_turns()}
            if any(turns.get(t, {}).get('status') == 'running' for t in session['turn_ids']):
                raise OperationError('drill_busy', 'Wait for the teacher to finish replying')
            text = (message or '').strip()
            identifier = turn_id or 'drill-turn-' + str(uuid.uuid4())
            self.operation({'op': 'drill.add_turn', 'id': session_id, 'turn_id': identifier, 'message': text})
            # The learner's own words are teaching interactions, as a lesson request is; More questions is not.
            self.host.start_turn({'id': identifier, 'concept_id': session['sections'][0], 'channel': 'drill',
                                  'record_user': bool(text), 'prompt': text or prompts.DRILL_START})
            return {'session': self._session(session_id)}

    def owner(self, turn_id):
        return next((s for s in self.state() if turn_id in s['turn_ids']), None)

    def _scope_data(self, session):
        model = self.operation({'op': 'curriculum.view'})
        titles = {c['id']: c['title'] for c in model['concepts']}
        points = {v['concept_id']: v['points'] for v in self.operation({'op': 'key_points.view'})['key_points']}
        return [{'id': cid, 'title': titles.get(cid, cid),
                 'key_points': [{k: p[k] for k in ('statement', 'holds_when', 'common_mistake') if k in p} for p in points.get(cid, [])]}
                for cid in session['sections']]

    def _review_state(self, session):
        covered = set(session['sections'])
        context = self.operation({'op': 'review.context', 'sections': session['sections']})
        mistakes = [{k: m[k] for k in ('kind', 'concept_ids', 'question', 'part', 'idea', 'answer', 'feedback', 'chosen') if m.get(k)}
                    for m in self.operation({'op': 'mistakes.list'})['entries'] if not m['right_at'] and covered & set(m['concept_ids'])]
        return {'sections': context['sections'], 'open_mistakes': mistakes[:OPEN_MISTAKES], 'earlier_review_questions': context['earlier']}

    def _conversation(self, session, current):
        """The session's earlier turns: what the learner said, what the teacher replied, and how each question went."""
        tasks = {t['id']: t for t in self.host.review.state()['tasks']}
        found = []
        for turn_id in session['turn_ids']:
            if turn_id == current:
                break
            turn = self.operation({'op': 'stream.read', 'id': turn_id})['turn']
            asked = [tasks[i] for i in session['task_ids'] if i.startswith(turn_id + ':') and i in tasks]
            found.append({'learner': '' if turn['prompt'] == prompts.DRILL_START else turn['prompt'],
                          'teacher': BLOCK.sub('', turn.get('final_text') or '').strip(),
                          'questions': [{'question': t['question'], 'kind': t.get('kind', 'apply'), 'outcome': self._outcome(t)} for t in asked]})
        return found[-CONVERSATION:]

    @staticmethod
    def _outcome(task):
        if task.get('answer'):
            return 'right' if task['answer']['correct'] else 'missed'
        assessed = [h for h in task.get('history', []) if h.get('action') == 'assess']
        if not assessed:
            return 'unanswered'
        last = assessed[-1]
        return 'right' if last.get('outcome') == 'passed' else 'missed: ' + (last.get('feedback') or '')[:400]

    def job_prompt(self, turn):
        session = self.owner(turn['id'])
        if session is None:
            raise OperationError('unknown_session', 'This drill turn has no session')
        language = turn.get('language', 'en')
        title = None
        if session['kind'] == 'warm_up':
            title = next((c['title'] for c in self.operation({'op': 'curriculum.view'})['concepts'] if c['id'] == session.get('concept_id')), None)
        instructions = prompts.drill_instructions(language, self._scope_data(session), session['kind'], title)
        message = turn['prompt']
        return prompts.Prompt(instructions, prompts.drill_request(self._review_state(session), self._conversation(session, turn['id']), message))

    def on_complete(self, turn):
        if turn['channel'] != 'drill':
            return
        session = self.owner(turn['id'])
        reply = tagged_json(QUESTIONS, turn['final_text'])
        if not session or not isinstance(reply, dict) or not reply.get('questions'):
            return
        try:
            self.operation({'op': 'drill.questions', 'id': session['id'], 'turn_id': turn['id'], 'questions': reply['questions']})
        except OperationError as exc:
            log.info('Drill turn %s wrote no usable questions: %s', turn['id'], exc)

    def fast(self, turn):
        """Whether a turn belongs to a drill: its own, or the assessment of an answer to one of its questions."""
        if turn['channel'] == 'drill':
            return True
        if turn['channel'] != 'practice':
            return False
        job = self.practice_job(turn['id'])
        if not job or not job.get('task_id'):
            return False
        task = next((t for t in self.host.review.state()['tasks'] if t['id'] == job['task_id']), None)
        return bool(task and task.get('session_id'))
