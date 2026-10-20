"""Course features served by the host. Each may add prompt text and react to turn lifecycle."""
import hashlib
import importlib.util
import io
import json
import re
import threading
import uuid
from pathlib import Path

from ..curriculum import source_unit
from ..store import OperationError, Store
from . import prompts

DECISION = re.compile(r'<teaching-decision>\s*(\{.*?\})\s*</teaching-decision>\s*$', re.S)
_PDF_LOCK = threading.Lock()


def renderer_available():
    return importlib.util.find_spec('pypdfium2') is not None and importlib.util.find_spec('PIL') is not None


def render_pdf_page(data, page_number):
    if not renderer_available():
        raise OperationError('renderer_unavailable', 'Original page image unavailable: install the project pdf extra, or use the original PDF link.')
    # PDFium forbids concurrent API calls, even for different documents.
    with _PDF_LOCK:
        import pypdfium2
        try:
            with pypdfium2.PdfDocument(data) as document:
                if not isinstance(page_number, int) or not 1 <= page_number <= len(document):
                    raise OperationError('invalid_reference', 'Invalid PDF page')
                page = document[page_number - 1]
                try:
                    width, height = page.get_size()
                    bitmap = page.render(scale=min(2.0, 1800 / max(width, height)))
                    try:
                        image = bitmap.to_pil()
                        try:
                            output = io.BytesIO()
                            image.save(output, format='PNG')
                            return output.getvalue()
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError('render_failed', 'Original page rendering failed; check the original PDF link.') from exc


def source_url(ref, fmt=None):
    url = f"/api/sources/{ref['source_id']}/{ref['revision']}/{ref['unit_id']}"
    return url + (f'?format={fmt}' if fmt else '')


def matching_ref(item, ref):
    return all(item.get(k) == ref[k] for k in ('source_id', 'revision', 'unit_id'))


class Feature:
    def __init__(self, host):
        self.host = host

    def operation(self, request):
        return self.host.operation(request)

    def prompt(self, turn, context):
        return ''

    def before_start(self, request):
        pass

    def on_complete(self, turn):
        pass


class Navigation(Feature):
    def preview(self, concept_id=None):
        request = {'op': 'curriculum.context'}
        if concept_id:
            request['concept_id'] = concept_id
        context = self.operation(request)
        model = self.operation({'op': 'curriculum.view'})
        concept = context['concept']
        index = model['route'].index(concept['id'])
        previous = next((c for c in model['concepts'] if index and c['id'] == model['route'][index - 1]), None)
        following = next((c for c in model['concepts'] if c['id'] == context['next_concept_id']), None)
        overview = concept.get('overview') if isinstance(concept.get('overview'), dict) else {}
        title = concept['title']
        if context['prerequisites']:
            prior = 'Builds on ' + ', '.join(c['title'] for c in context['prerequisites'])
        else:
            prior = 'Continues from ' + previous['title'] if previous else 'Start with the fundamental questions of this course'
        context['overview'] = {
            'core_problem': overview.get('core_problem') or concept.get('core_question') or f'How can we understand {title} and what problem does it solve?',
            'steps': overview.get('steps') or [f'Develop an intuitive picture of {title}', 'Identify key relationships, notation, and conditions', 'Check understanding with an example, then try exercises'],
            'prior': overview.get('prior') or prior,
            'next': overview.get('next') or ('Prepares for ' + following['title'] if following else 'Review this unit and apply the concepts to combined problems'),
            'target_ability': overview.get('target_ability') or concept.get('objective') or concept.get('goal') or f'Explain {title} and apply it to related problems',
            'origin': 'teacher' if overview else 'route_summary',
        }
        for source in context['sources']:
            mapping = next((m for m in model['coverage'] if matching_ref(m, source)), {})
            source['verification'] = mapping.get('verification', 'pending')
            source['url'] = source_url(source)
        return context

    def source(self, source_id, revision, unit_id, fmt=None):
        ref = {'source_id': source_id, 'revision': revision, 'unit_id': unit_id}
        if not re.fullmatch(r'src-[0-9a-f]{24}', source_id) or not re.fullmatch(r'[0-9a-f]{64}', revision):
            raise OperationError('invalid_reference', 'Choose a registered source revision')
        snapshot = self.operation({'op': 'source.read', **ref})
        unit = next((u for u in snapshot['units'] if u['id'] == unit_id), None)
        if unit is None:
            raise OperationError('invalid_reference', 'Unknown source location')
        root = (self.host.workspace / 'sources').resolve()
        path = (root / source_id / revision).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise OperationError('unavailable_source', 'Source snapshot unavailable')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != revision:
            raise OperationError('unavailable_source', 'Source snapshot integrity check failed')
        kind = Path(snapshot['path']).suffix.lower()
        page = unit.get('locator', {}).get('page')
        if fmt == 'image':
            if kind != '.pdf':
                raise OperationError('invalid_reference', 'Only PDF pages have rendered previews')
            return render_pdf_page(data, page), 'image/png'
        if fmt == 'pdf':
            if kind != '.pdf':
                raise OperationError('invalid_reference', 'Only registered PDF snapshots can be opened directly')
            return data, 'application/pdf'
        if fmt:
            raise OperationError('invalid_reference', 'Unknown source format')
        model = self.operation({'op': 'curriculum.view'})
        mapping = next((m for m in model['coverage'] if matching_ref(m, ref)), {})
        current = next((s for s in self.operation({'op': 'course.status'})['sources'] if s['id'] == source_id), {})
        available = renderer_available()
        return {**ref, **unit, 'title': Path(snapshot['path']).name, 'kind': kind,
                'verification': mapping.get('verification', 'pending'), 'stale': current.get('revision') != revision,
                'image_url': source_url(ref, 'image') if kind == '.pdf' and page and available else None,
                'render_message': None if available else 'Original page image unavailable: install the project pdf extra. You can still open the original PDF.',
                'pdf_url': source_url(ref, 'pdf') + f'#page={page}' if kind == '.pdf' and page else None,
                'document': None if kind == '.pdf' else [{'id': u['id'], 'text': u.get('text', '')} for u in snapshot['units']]}

    def prompt(self, turn, context):
        if turn['channel'] != 'mainline':
            return ''
        earlier = [t for t in self.host.turns() if t['id'] != turn['id'] and t['channel'] == 'mainline'
                   and t['concept_id'] == turn['concept_id'] and t['status'] == 'completed']
        return prompts.LESSON_CONTINUES if earlier else prompts.LESSON_FIRST


class Questions(Feature):
    """Side questions asked from the lesson; they never move the teaching mainline on their own."""

    def list(self):
        return self.operation({'op': 'branch.list'})['branches']

    def ask(self, body):
        with self.host.lock:
            identifier = body.get('id') or str(uuid.uuid4())
            main_id = body.get('main_turn_id')
            if main_id:
                main = self.operation({'op': 'stream.read', 'id': main_id})['turn']
                if main['channel'] != 'mainline':
                    raise OperationError('invalid_mainline', 'Expected mainline turn')
            branch = self.operation({**body, 'op': 'branch.begin', 'id': identifier})['branch']
            if body.get('pause') is True and branch.get('main_turn_id'):
                self.host.pause_turn(branch['main_turn_id'])
            result = self.host.start_turn({'id': branch['turn_id'], 'channel': 'sidequestion',
                                           'concept_id': branch['restore_point']['concept_id'], 'prompt': branch['question']})
            self.host.changed()
            return {'branch': branch, **result}

    def choose(self, identifier, choice):
        with self.host.lock:
            branch = self.operation({'op': 'branch.read', 'id': identifier})['branch']
            if choice == 'accept' and branch['status'] == 'suggested':
                if self.operation({'op': 'course.status'})['position'] != branch['restore_point']:
                    raise OperationError('stale_branch', 'Mainline changed')
                if branch.get('main_turn_id'):
                    self.host.pause_turn(branch['main_turn_id'])
            branch = self.operation({'op': 'branch.choose', 'id': identifier, 'choice': choice})['branch']
            if branch['choice'] == 'accept':
                self.host.start_turn({'id': branch['supplement_turn_id'], 'concept_id': branch['restore_point']['concept_id'],
                                      'channel': 'sidequestion', 'record_user': False,
                                      'prompt': prompts.supplement_request(branch['decision']['supplement_goal'])})
            self.host.changed()
            return {'branch': branch}

    def return_to_mainline(self, identifier):
        result = self.operation({'op': 'branch.return', 'id': identifier})
        self.host.changed()
        return result

    def _branch_for(self, turn):
        return next((b for b in self.list() if turn['id'] in (b['turn_id'], b.get('supplement_turn_id'))), None)

    def prompt(self, turn, context):
        branch = self._branch_for(turn)
        if not branch:
            return ''
        branch = turn.get('prompt_snapshot', {}).get('branch', branch)
        main_text = self.operation({'op': 'stream.read', 'id': branch['main_turn_id']})['turn']['text'] if branch.get('main_turn_id') else None
        common = prompts.question_context(branch, main_text)
        if turn['id'] == branch.get('supplement_turn_id'):
            return common + prompts.SUPPLEMENT
        return common + prompts.QUESTION_PROTOCOL

    def on_complete(self, turn):
        if not turn['id'].startswith('branch:'):
            return
        match = DECISION.search(turn['final_text'])
        if not match:
            return  # the question stays unanswered when the decision is missing
        try:
            decision = json.loads(match.group(1))
            branch = self.operation({'op': 'branch.decide', 'id': turn['id'].removeprefix('branch:'), 'decision': decision})['branch']
        except (ValueError, OperationError):
            return
        if decision.get('mainline_error') is True and branch.get('main_turn_id'):
            self.host.pause_turn(branch['main_turn_id'])

    def recover(self):
        """Close the gap between a saved completion and its decision after a crash, without a model call."""
        for turn in self.host.turns():
            if turn['status'] == 'completed':
                self.on_complete(turn)


class Practice(Feature):
    ACTIONS = ('hint', 'steps', 'solution', 'assess', 'defer')

    def state(self):
        # Reconcile jobs completed just before a crash, before their completion hook ran.
        for job in self.operation({'op': 'practice.list'})['jobs']:
            if not job.get('processed'):
                self.operation({'op': 'practice.complete', 'id': job['id']})
        return self.operation({'op': 'practice.list'})

    def _launch(self, concept_id, action, task=None, answer=None):
        with self.host.lock:
            jobs = self.state()['jobs']
            running = {t['id'] for t in self.host.turns() if t['status'] == 'running'}
            for job in jobs:
                if job['id'] not in running:
                    continue
                if (job.get('task_id') == task['id']) if task else (job['concept_id'] == concept_id and job['action'] == 'generate'):
                    raise OperationError('practice_busy', 'Wait for the current practice request to finish')
            identifier = 'practice-' + str(uuid.uuid4())
            job = {'id': identifier, 'concept_id': concept_id, 'action': action}
            if task:
                job['task_id'] = task['id']
            if answer is not None:
                if not isinstance(answer, str) or not answer.strip():
                    raise OperationError('empty_answer', 'Enter your reasoning or answer first')
                job['answer'] = answer
            self.operation({'op': 'practice.job', 'job': job})
            return self.host.start_turn({'id': identifier, 'concept_id': concept_id, 'channel': 'practice',
                                         'record_user': False, 'prompt': prompts.PRACTICE_REQUEST})

    def generate(self, concept_id):
        existing = [t for t in self.state()['tasks'] if t['concept_id'] == concept_id]
        if existing:
            return {'tasks': existing}
        return self._launch(concept_id, 'generate')

    def act(self, task_id, action, answer=None):
        task = next((t for t in self.state()['tasks'] if t['id'] == task_id), None)
        if not task:
            raise OperationError('unknown_exercise', 'Unknown exercise')
        if action not in self.ACTIONS:
            raise OperationError('invalid_action', 'Unknown practice action')
        if action == 'defer':
            with self.host.lock:
                for job in self.state()['jobs']:
                    if job.get('task_id') == task['id'] and not job.get('processed'):
                        try:
                            self.host.pause_turn(job['id'])
                        except OperationError as exc:
                            if exc.code != 'unknown_turn':
                                raise
                result = self.operation({'op': 'practice.defer', 'id': task['id']})
                self.host.changed()
                return result
        return self._launch(task['concept_id'], action, task, answer if action == 'assess' else None)

    def next_section(self, concept_id, request_id):
        with self.host.lock:
            session = self.operation({'op': 'session.resume'})
            if session.get('active_branch'):
                raise OperationError('active_branch', 'Return to the teaching mainline before entering the next section')
            if any(b.get('choice') == 'accept' and not b.get('returned') for b in self.host.questions.list()):
                raise OperationError('active_branch', 'Return to the teaching mainline first')
            current = session.get('position') or {}
            if current.get('concept_id') not in (None, concept_id):
                raise OperationError('stale_position', 'The current position has changed; refresh the page')
            target = self.operation({'op': 'curriculum.context', 'concept_id': concept_id})['next_concept_id']
            if not target:
                return {'finished': True}
            for turn in self.host.turns():
                if turn['concept_id'] == concept_id and turn['status'] == 'running':
                    self.host.pause_turn(turn['id'])
            concept = self.operation({'op': 'curriculum.context', 'concept_id': target})['concept']
            result = self.operation({'op': 'mainline.enter', 'request_id': request_id, 'concept_id': target,
                                     'goal': concept['title'], 'next_step': 'Begin teaching this section', 'progress': ''})
            self.host.changed()
            return result

    def _sources(self, refs):
        store = Store(self.host.workspace)
        try:
            return [{**ref, 'unit': source_unit(store, ref)} for ref in refs]
        finally:
            store.db.close()

    def prompt(self, turn, context):
        state = self.operation({'op': 'practice.list'})
        job = next((j for j in state['jobs'] if j['id'] == turn['id']), None)
        if not job:
            return ''
        if job['action'] == 'generate':
            # Exercise refs need not be included in the lesson links.
            return prompts.practice_generate(self._sources(context['concept'].get('exercises', [])))
        task = next(t for t in state['tasks'] if t['id'] == job['task_id'])
        return prompts.practice_feedback(job['action'], task, self._sources(task['source_refs']), job.get('answer'))

    def on_complete(self, turn):
        self.operation({'op': 'practice.complete', 'id': turn['id']})
        if turn['channel'] == 'mainline' and not self.host.closing:
            self.generate(turn['concept_id'])


class Preparation(Feature):
    """Prepares the next section only while the learner's own work is idle."""

    def __init__(self, host):
        super().__init__(host)
        self.operation({'op': 'preparation.recover'})
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='preparation')
        self._last = None

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def join(self, timeout):
        if self._thread.is_alive():
            self._thread.join(timeout)

    def state(self, concept_id=None):
        request = {'op': 'preparation.view'}
        if concept_id:
            request['concept_id'] = concept_id
        return self.operation(request)

    def before_start(self, request):
        if request.get('channel', 'mainline') == 'preparation':
            return
        for turn in self.host.turns():
            if turn['channel'] == 'preparation' and turn['status'] == 'running':
                self.host.pause_turn(turn['id'])
        self.operation({'op': 'preparation.reconcile'})

    def prompt(self, turn, context):
        if turn['channel'] == 'preparation':
            job = next(j for j in self.state()['jobs'] if j['id'] == turn['id'])
            return prompts.preparation_task(job['snapshot']['context'])
        material = self.state(turn['concept_id'])['ready']
        return prompts.preparation_material(material['content']) if material else prompts.PREPARATION_MISSING

    def schedule(self, retry=False):
        with self.host.lock:
            if self.host.closing:
                return {'scheduled': False, 'reason': 'host_closing'}
            stale = {j['id'] for j in self.state()['jobs'] if j['status'] == 'stale'}
            for turn in self.host.turns():
                if turn['id'] in stale and turn['status'] == 'running':
                    self.host.pause_turn(turn['id'])
            turns = self.host.turns()
            # A paused process can still be shutting down; never start a second preparation process.
            if any(t['status'] == 'running' for t in turns) or any(t['channel'] == 'preparation' and self.host.worker_alive(t) for t in turns):
                return {'scheduled': False, 'reason': 'foreground_or_worker_active'}
            values = self.state()
            concept_id = values['next_concept_id']
            if not concept_id:
                return {'scheduled': False, 'reason': 'no_next_section'}
            relevant = [j for j in values['jobs'] if j['concept_id'] == concept_id]
            if any(j['status'] == 'ready' for j in relevant):
                return {'scheduled': False, 'reason': 'ready'}
            # Failed attempts need an explicit retry rather than an unbounded model loop.
            if relevant and relevant[-1]['status'] == 'failed' and not retry:
                return {'scheduled': False, 'reason': 'failed'}
            result = self.operation({'op': 'preparation.enqueue', 'id': 'preparation-' + str(uuid.uuid4())})
            if not result['created']:
                return {'scheduled': False, 'reason': 'existing'}
            try:
                return self.host.start_turn({'id': result['job']['id'], 'concept_id': concept_id, 'channel': 'preparation',
                                             'record_user': False, 'prompt': prompts.PREPARATION_REQUEST})
            except Exception:
                self.operation({'op': 'preparation.recover'})
                raise

    def _loop(self):
        while not self._stop.wait(.35):
            if self.host.closing:
                return
            try:
                self.schedule()
                summary = [(j['id'], j['status']) for j in self.state()['jobs']]
                if summary != self._last:
                    self._last = summary
                    self.host.changed('preparation')
            except OperationError:
                if self.host.closing:
                    return
                # Invalid or changing course sources never block the teacher.
                continue
