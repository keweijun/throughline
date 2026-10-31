"""Course features served by the host. Each may add prompt text and react to turn lifecycle."""
import hashlib
import importlib.util
import io
import json
import logging
import re
import threading
import uuid
from pathlib import Path

from .. import lessons
from .. import practice
from .. import images as attached
from .. import review
from ..store import OperationError
from .. import memory
from ..streaming import BACKGROUND, PREPARED_STEP
from . import prompts

log = logging.getLogger(__name__)

RETRIEVAL_ORIGINS = ('review', 'chapter_quiz')
DECISION = re.compile(r'<teaching-decision>\s*(\{.*?\})\s*</teaching-decision>\s*$', re.S)
STEP_REPLY = re.compile(r'<lesson-step>\s*(\{.*?\})\s*</lesson-step>', re.S)
STEP_BLOCK = re.compile(r'\s*<lesson-step>.*$', re.S)
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


def is_recap(turn):
    return turn['id'].startswith('recap:')


def missed_check(step):
    """A step's check question answered wrongly or with "not sure", as the next step's prompt repairs it; else None."""
    check, answer = step.get('check'), step.get('answer')
    if not check or not answer or answer['correct']:
        return None
    right = check['options'][check['correct']]
    missed = {'idea': check['idea'], 'question': check['question'], 'correct_answer': right['text'], 'why': right['explanation']}
    if answer['unsure']:
        return {**missed, 'unsure': True}
    chosen = check['options'][answer['choice']]
    return {**missed, 'chosen': chosen['text'], 'what_the_choice_suggests': chosen['explanation']}


def chapter_owned(item):
    """A chapter recap turn or chapter quiz question: listed on the chapter page, never among a section's lessons or
    exercises. Its concept_id is the chapter's last section, kept only as the anchor that section-scoped records
    (stream context, side-question restore points, annotations, practice and evidence) need (ADR 0006)."""
    return bool(item.get('chapter_id'))


def matching_ref(item, ref):
    return all(item.get(k) == ref[k] for k in ('source_id', 'revision', 'unit_id'))


# Shown for a section the teacher has not written an overview for, in the course language.
OVERVIEW_FALLBACK = {
    'en': {'builds_on': 'Builds on {}', 'separator': ', ', 'continues': 'Continues from {}',
           'start': 'Start with the fundamental questions of this course',
           'core_problem': 'How can we understand {} and what problem does it solve?',
           'steps': ['Develop an intuitive picture of {}', 'Identify key relationships, notation, and conditions',
                     'Check understanding with an example, then try exercises'],
           'prepares': 'Prepares for {}', 'review': 'Review this section and apply the concepts to combined problems',
           'target_ability': 'Explain {} and apply it to related problems'},
    'zh-CN': {'builds_on': '建立在{}之上', 'separator': '、', 'continues': '承接{}',
              'start': '从本课程最基本的问题开始',
              'core_problem': '如何理解{}？它解决什么问题？',
              'steps': ['建立对{}的直观理解', '弄清关键关系、记号和适用条件', '用例题检验理解，然后做练习'],
              'prepares': '为{}做准备', 'review': '复习本小节，并把这些概念用于综合问题',
              'target_ability': '能够解释{}并用它解决相关问题'},
}


def parse_json(text):
    """A model's JSON reply, with or without a code fence; ValueError when it is not JSON."""
    raw = (text or '').strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
    return json.loads(raw)


def tagged_json(pattern, text):
    """The JSON object a reply carries in a tagged block (`pattern` captures it), or None when it is missing or invalid."""
    match = pattern.search(text or '')
    try:
        return json.loads(match.group(1)) if match else None
    except ValueError:
        return None


class Feature:
    def __init__(self, host):
        self.host = host

    def operation(self, request):
        return self.host.operation(request)

    def prompt(self, turn, context):
        return ''

    def before_start(self, request):
        pass

    def images(self, turn):
        """Local image files sent to the teacher with this turn's prompt."""
        return []

    def practice_job(self, identifier):
        return next((j for j in self.operation({'op': 'practice.list'})['jobs'] if j['id'] == identifier), None)

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
        chinese = self.operation({'op': 'preferences.view'})['preferences']['language'] == 'zh-CN'
        text = OVERVIEW_FALLBACK['zh-CN' if chinese else 'en']
        title = concept['title']
        if context['prerequisites']:
            prior = text['builds_on'].format(text['separator'].join(c['title'] for c in context['prerequisites']))
        else:
            prior = text['continues'].format(previous['title']) if previous else text['start']
        context['overview'] = {
            'core_problem': overview.get('core_problem') or concept.get('core_question') or text['core_problem'].format(title),
            'steps': overview.get('steps') or [step.format(title) for step in text['steps']],
            'prior': overview.get('prior') or prior,
            'next': overview.get('next') or (text['prepares'].format(following['title']) if following else text['review']),
            'target_ability': overview.get('target_ability') or concept.get('objective') or concept.get('goal') or text['target_ability'].format(title),
            'origin': 'teacher' if overview else 'route_summary',
        }
        context['set_aside'] = [{**{k: m[k] for k in ('source_id', 'revision', 'unit_id')}, 'disposition': m['disposition'], 'reason': m.get('reason', '')}
                                for m in model['coverage'] if m.get('disposition') in ('deferred', 'needs_review') and concept['id'] in m.get('concept_ids', [])]
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

    def _due(self, turn):
        # The explanations frozen into this turn's snapshot are the ones this lesson was asked to give.
        due = {i['id'] for i in (turn.get('prompt_snapshot') or {}).get('session', {}).get('due_explanations', [])}
        return [i for i in self.operation({'op': 'deferred.list'})['deferred_explanations'] if i['id'] in due]

    def prompt(self, turn, context):
        if turn['channel'] not in ('mainline', PREPARED_STEP):
            return ''
        language = turn.get('language', 'en')
        chapter = context.get('chapter')
        if is_recap(turn):
            return prompts.chapter_recap(chapter, *self._recap_data(chapter), language)
        lesson, number, repair = self._step(turn)
        earlier = [t for t in self.host.brief_turns() if t['id'] != turn['id'] and t['channel'] == 'mainline'
                   and t['concept_id'] == turn['concept_id'] and t['status'] == 'completed' and not chapter_owned(t)]
        if earlier and not lesson:
            text = prompts.LESSON_CONTINUES
        elif number and number > 1:
            text = ''
        else:
            # Every routed section is in a chapter: flat routes become one chapter (ADR 0006, migration 3).
            text = prompts.chapter_lesson(chapter, chapter['concept_ids'][0] == turn['concept_id'], language) + '\n'
        if lesson:
            previous = [{'step': i + 1, 'title': s['title'], 'text': self._step_text(s['turn_id'])} for i, s in enumerate(lesson['steps'][:number - 1])]
            text += prompts.lesson_step(lesson['steps'], number, previous, lesson.get('request'), lessons.MAX_STEPS, repair) + '\n'
        text += prompts.SECTION_FOCUS
        due = [i for i in self._due(turn) if i['status'] == 'pending']
        return text + '\n' + prompts.due_explanations(due) if due else text

    def _step_text(self, turn_id):
        return STEP_BLOCK.sub('', self.operation({'op': 'stream.read', 'id': turn_id})['turn']['final_text'] or '')

    def _step(self, turn):
        """The lesson, step number and check repair a step's prompt teaches: a prepared step keeps those its snapshot
        recorded, so Continue reveals exactly what it assumed."""
        ahead = (turn.get('prompt_snapshot') or {}).get('lesson_step')
        if ahead:
            return self.operation({'op': 'lesson.read', 'id': ahead['lesson_id']})['lesson'], ahead['number'], ahead['missed_check']
        lesson, number = self.step_of(turn['id'])
        return lesson, number, missed_check(lesson['steps'][number - 2]) if lesson and number > 1 else None

    def step_of(self, turn_id):
        """The stepped lesson a turn teaches a step of, and the step's number; (None, None) for a single-reply lesson."""
        for lesson in self.operation({'op': 'lesson.list'})['lessons']:
            for index, step in enumerate(lesson['steps']):
                if step.get('turn_id') == turn_id:
                    return lesson, index + 1
        return None, None

    def steps_remain(self, turn):
        """Whether the stepped lesson this turn belongs to still has steps to teach after it."""
        lesson, number = self.step_of(turn['id'])
        return bool(lesson) and number < len(lesson['steps'])

    def start_lesson(self, concept_id, body):
        """A section's first lesson is taught in steps planned from its overview (ADR 0009); a later request over a
        section that already has a lesson, including one saved before steps, is a single reply."""
        identifier = body.get('id') or str(uuid.uuid4())
        prompt = (body.get('prompt') or '').strip()
        with self.host.lock:
            existing = self._existing(identifier)
            if existing:
                return existing
            taught = any(t['channel'] == 'mainline' and t['concept_id'] == concept_id and not chapter_owned(t) for t in self.host.brief_turns())
            if taught:
                return self.host.start_turn({'id': identifier, 'concept_id': concept_id, 'channel': 'mainline', 'prompt': prompt or prompts.DEFAULT_LESSON_REQUEST})
            self.host.ensure_single_mainline(identifier, 'Pause the current lesson before starting another')
            preview = self.preview(concept_id)
            prompt = prompt or prompts.STEP_LESSON_REQUEST
            # The teacher plans the steps in its first reply; the section overview reaches it as course data, and its steps
            # are only the fallback when that reply plans none.
            outline = [s.strip()[:lessons.MAX_TITLE] for s in preview['overview']['steps'] if isinstance(s, str) and s.strip()][:lessons.MAX_STEPS]
            self.operation({'op': 'lesson.begin', 'id': identifier, 'concept_id': concept_id, 'request': prompt,
                            'steps': [preview['concept']['title'][:lessons.MAX_TITLE]], 'outline': outline})
            return self._start_step(identifier, identifier, concept_id, prompt)

    def continue_lesson(self, lesson_id, body):
        """Continue: teach the next planned step of a lesson in the current section."""
        identifier = body.get('id') or str(uuid.uuid4())
        with self.host.lock:
            lesson = self.operation({'op': 'lesson.read', 'id': lesson_id})['lesson']
            existing = self._existing(identifier)
            if existing:
                return existing
            position = self.operation({'op': 'course.status'})['position'] or {}
            if position.get('concept_id') != lesson['concept_id']:
                raise OperationError('stale_position', 'This lesson belongs to another section; refresh the page')
            done = next((s for s in lesson['steps'] if s.get('request_id') == identifier), None)
            if done:
                return {'turn': self.operation({'op': 'stream.read', 'id': done['turn_id']})['turn'], 'created': False}
            self.host.ensure_single_mainline(identifier, 'Pause the current lesson before starting another')
            prepared = self._prepared(lesson)
            if not prepared:
                self.discard_prepared()
                return self._start_step(lesson_id, identifier, lesson['concept_id'], prompts.STEP_CONTINUE_REQUEST)
            self.operation({'op': 'lesson.step', 'id': lesson_id, 'turn_id': prepared['id'], 'request_id': identifier})
            turn = self.operation({'op': 'stream.read', 'id': prepared['id']})['turn']
            self.host.publish_turn(turn)
            if turn['status'] == 'completed':
                self.host.completed(turn)
            self.host.changed()
            return {'turn': turn, 'created': True, 'prepared': True}

    def answer_check(self, lesson_id, turn_id, choice):
        """A check answer shows its explanation at once: it is recorded, with no model turn (ADR 0009). A miss means the
        next step opens with a repair, so the step prepared without one is written again."""
        with self.host.lock:
            result = self.operation({'op': 'lesson.answer', 'id': lesson_id, 'turn_id': turn_id, 'choice': choice})
            if result['changed'] and not result['answer']['correct']:
                self.prepare(result['lesson'])
        if result['changed']:
            self.host.changed()
        return {'answer': result['answer'], 'changed': result['changed']}

    def prepare(self, lesson):
        """Start writing the lesson's next step while the learner reads the current one, replacing any prepared step. It
        is hidden until Continue; nothing is prepared after the last step, outside the current section, or while another
        lesson is being written."""
        with self.host.lock:
            self.discard_prepared()
            lesson = self.operation({'op': 'lesson.read', 'id': lesson['id']})['lesson']
            taught = [s for s in lesson['steps'] if s.get('turn_id')]
            turns = {t['id']: t for t in self.host.brief_turns()}
            position = self.operation({'op': 'course.status'})['position'] or {}
            if (self.host.closing or not taught or len(taught) == len(lesson['steps']) or position.get('concept_id') != lesson['concept_id']
                    or turns.get(taught[-1]['turn_id'], {}).get('status') != 'completed'
                    or any(t['channel'] == 'mainline' and t['status'] == 'running' for t in turns.values())):
                return None
            identifier = 'step:' + str(uuid.uuid4())
            self.host.start_turn({'id': identifier, 'concept_id': lesson['concept_id'], 'channel': PREPARED_STEP, 'record_user': False,
                                  'prompt': prompts.STEP_CONTINUE_REQUEST,
                                  'lesson_step': {'lesson_id': lesson['id'], 'number': len(taught) + 1, 'missed_check': missed_check(taught[-1])}})
            self.operation({'op': 'lesson.prepare', 'id': lesson['id'], 'turn_id': identifier})
            return identifier

    def _prepared(self, lesson):
        """The lesson's prepared step, still running or complete, when its prompt still applies: the next step, with the
        repair the last check now calls for, in the current language."""
        if not lesson.get('prepared'):
            return None
        turn = self.operation({'op': 'stream.read', 'id': lesson['prepared']})['turn']
        ahead = turn['prompt_snapshot'].get('lesson_step') or {}
        taught = [s for s in lesson['steps'] if s.get('turn_id')]
        language = self.operation({'op': 'preferences.view'})['preferences']['language']
        if (turn['channel'] == PREPARED_STEP and turn['status'] in ('running', 'completed') and taught and ahead.get('number') == len(taught) + 1
                and ahead.get('missed_check') == missed_check(taught[-1]) and turn.get('language', 'en') == language):
            return turn
        return None

    def discard_prepared(self):
        """Drop every prepared step, stopping any still being written."""
        with self.host.lock:
            for lesson in self.operation({'op': 'lesson.list'})['lessons']:
                if lesson.get('prepared'):
                    self.operation({'op': 'lesson.prepare', 'id': lesson['id'], 'turn_id': None})
            for turn in self.host.brief_turns():
                if turn['channel'] == PREPARED_STEP and turn['status'] == 'running':
                    self.host.pause_turn(turn['id'])

    def before_start(self, request):
        if request.get('channel', 'mainline') == 'mainline':
            self.discard_prepared()  # another lesson, or a step regenerated, goes first

    def _existing(self, identifier):
        """A retried request whose turn already started."""
        try:
            turn = self.operation({'op': 'stream.read', 'id': identifier})['turn']
        except OperationError:
            return None
        if turn['channel'] != 'mainline':
            raise OperationError('id_conflict', identifier)
        return {'turn': turn, 'created': False}

    def _start_step(self, lesson_id, identifier, concept_id, prompt):
        self.operation({'op': 'lesson.step', 'id': lesson_id, 'turn_id': identifier})
        return self.host.start_turn({'id': identifier, 'concept_id': concept_id, 'channel': 'mainline', 'prompt': prompt})

    def _record_step(self, lesson, turn):
        """Read the plan block a completed step ends with. A missing or invalid block keeps the plan as it was; an invalid
        check question is dropped and an invalid plan kept, each without losing the other."""
        request = {'op': 'lesson.reply', 'id': lesson['id'], 'turn_id': turn['id']}
        reply = tagged_json(STEP_REPLY, turn['final_text'])
        fields = {k: reply[k] for k in ('title', 'remaining', 'check') if k in reply} if isinstance(reply, dict) else {}
        while True:
            try:
                return self.operation({**request, **fields})
            except OperationError as exc:
                dropped = {'invalid_plan': ('title', 'remaining'), 'invalid_check': ('check',)}.get(exc.code)
                if not any(k in fields for k in dropped or ()):
                    raise
                log.info('Step %s returned an invalid reply: %s', turn['id'], exc)
                fields = {k: v for k, v in fields.items() if k not in dropped}

    def recover(self):
        """Read the plans of steps completed just before a crash, without a model call."""
        for lesson in self.operation({'op': 'lesson.list'})['lessons']:
            for step in lesson['steps']:
                if step.get('turn_id') and not step.get('replied'):
                    turn = next((t for t in self.host.brief_turns() if t['id'] == step['turn_id']), None)
                    if turn and turn['status'] == 'completed':
                        self._record_step(lesson, self.operation({'op': 'stream.read', 'id': turn['id']})['turn'])

    def _recap_data(self, chapter):
        model = self.operation({'op': 'curriculum.view'})
        titles = {c['id']: c['title'] for c in model['concepts']}
        deferred = [{'section': titles[t['concept_id']], 'question': t['question']}
                    for t in self.operation({'op': 'practice.list'})['tasks']
                    if t['status'] == 'deferred' and t['concept_id'] in chapter['concept_ids'] and not chapter_owned(t) and t['origin'] not in RETRIEVAL_ORIGINS]
        studied = set(self.studied(chapter))
        return ([titles[cid] for cid in chapter['concept_ids']], deferred,
                [titles[cid] for cid in chapter['concept_ids'] if cid not in studied])

    def chapter(self, chapter_id):
        chapter = next((c for c in self.operation({'op': 'curriculum.view'})['chapters'] if c['id'] == chapter_id), None)
        if chapter is None:
            raise OperationError('unknown_chapter', 'Unknown chapter')
        if not chapter['concept_ids']:
            raise OperationError('not_built', 'This chapter is not built yet')
        return chapter

    def studied(self, chapter):
        """The chapter's sections with a completed lesson of their own."""
        done = {t['concept_id'] for t in self.host.brief_turns() if t['channel'] == 'mainline' and t['status'] == 'completed' and not chapter_owned(t)}
        return [cid for cid in chapter['concept_ids'] if cid in done]

    def studied_chapter(self, chapter_id):
        """A chapter recap or quiz is offered once any section of the chapter has a completed lesson, wherever the learner is."""
        chapter = self.chapter(chapter_id)
        if not self.studied(chapter):
            raise OperationError('not_studied', 'Study a section of this chapter first')
        return chapter

    def start_recap(self, chapter_id, identifier=None):
        """A recap is a mainline turn owned by the chapter and shown on its page; it explains nothing new. Starting one
        never moves the learner's position, and like any lesson it waits while another lesson is being written."""
        with self.host.lock:
            chapter = self.studied_chapter(chapter_id)
            chinese = self.operation({'op': 'preferences.view'})['preferences']['language'] == 'zh-CN'
            return self.host.start_turn({'id': 'recap:' + (identifier or str(uuid.uuid4())).removeprefix('recap:'), 'concept_id': chapter['concept_ids'][-1],
                                         'chapter_id': chapter['id'], 'channel': 'mainline', 'prompt': prompts.recap_request(chapter['title'], chinese)})

    def on_complete(self, turn):
        if turn['channel'] != 'mainline' or is_recap(turn):
            return
        self.host.practice.resolve_skip(turn)
        lesson, _ = self.step_of(turn['id'])
        if lesson:
            self._record_step(lesson, turn)
            if self.steps_remain(turn):
                self.prepare(lesson)
                return  # pending explanations are given within the lesson, by its last step at the latest
        for item in self._due(turn):
            if item['status'] != 'pending':
                continue
            try:
                self.operation({'op': 'deferred.resolve', 'id': item['id'], 'answer_interaction_id': 'stream:' + turn['id']})
            except OperationError:
                continue


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

    def reply(self, identifier, body):
        with self.host.lock:
            result = self.operation({**body, 'op': 'branch.reply', 'id': identifier,
                                     'reply_id': body.get('id') or str(uuid.uuid4())})
            branch, reply = result['branch'], result['reply']
            started = self.host.start_turn({'id': reply['turn_id'], 'channel': 'sidequestion',
                                           'concept_id': branch['restore_point']['concept_id'], 'prompt': reply['question']})
            self.host.changed()
            return {**result, **started}

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
        return next((b for b in self.list() if turn['id'] in [b['turn_id'], b.get('supplement_turn_id')] + [r['turn_id'] for r in b.get('replies', [])]), None)

    def prompt(self, turn, context):
        branch = self._branch_for(turn)
        if not branch:
            return ''
        snapshot_branch = turn.get('prompt_snapshot', {}).get('branch')
        branch = snapshot_branch or branch
        main_text = self.operation({'op': 'stream.read', 'id': branch['main_turn_id']})['turn']['text'] if branch.get('main_turn_id') else None
        common = prompts.question_context(branch, main_text, in_snapshot=snapshot_branch is not None)
        if turn['id'].startswith('reply:'):
            return common + prompts.QUESTION_FOLLOWUP + attached.described(len(self._asked(branch, turn).get('images', [])), 'this follow-up')
        if turn['id'] == branch.get('supplement_turn_id'):
            return common + prompts.SUPPLEMENT
        return common + prompts.question_protocol(turn.get('language', 'en')) + attached.described(len(branch.get('images', [])), 'this question')

    @staticmethod
    def _asked(branch, turn):
        """The question or follow-up a turn answers; a supplement answers neither."""
        if turn['id'] == branch['turn_id']:
            return branch
        return next((r for r in branch.get('replies', []) if r['turn_id'] == turn['id']), {})

    def images(self, turn):
        if turn.get('channel') != 'sidequestion':
            return []
        branch = self._branch_for(turn)
        names = self._asked(branch, turn).get('images', []) if branch else []
        return [str(attached.path(self.host.workspace, name)) for name in names]

    def on_complete(self, turn):
        if not turn['id'].startswith('branch:'):
            return
        decision = tagged_json(DECISION, memory.strip(turn['final_text']))
        if not isinstance(decision, dict):
            return  # the question stays unanswered when the decision is missing
        try:
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
    ACTIONS = ('hint', 'steps', 'solution', 'assess', 'ask', 'defer', 'skip')

    def state(self):
        # Reconcile jobs completed just before a crash, before their completion hook ran.
        for job in self.operation({'op': 'practice.list'})['jobs']:
            if not job.get('processed'):
                try:
                    self.operation({'op': 'practice.complete', 'id': job['id']})
                except OperationError:
                    # The course refused the record (a conflicting ID, say); the job stays unprocessed rather than half-recorded.
                    log.warning('Practice job %s cannot be recorded', job['id'], exc_info=True)
        return self.operation({'op': 'practice.list'})

    def images(self, turn):
        job = self.practice_job(turn['id'])
        return [str(attached.path(self.host.workspace, name)) for name in (job or {}).get('images', [])]

    def _launch(self, concept_id, action, task=None, answer=None, purpose=None, chapter_id=None, question=None, images=None, request=None):
        with self.host.lock:
            jobs = self.state()['jobs']
            running = {t['id'] for t in self.host.brief_turns() if t['status'] == 'running'}
            for job in jobs:
                if job['id'] not in running:
                    continue
                # Review sets are independent of each other, so one being written never holds up another.
                if (job.get('task_id') == task['id']) if task else (job['concept_id'] == concept_id and job['action'] == 'generate' and job.get('purpose') == purpose and purpose != 'review'):
                    raise OperationError('practice_busy', 'Wait for the current practice request to finish')
            identifier = 'practice-' + str(uuid.uuid4())
            job = {'id': identifier, 'concept_id': concept_id, 'action': action, **(request or {})}
            if purpose:
                job['purpose'] = purpose
            if chapter_id:
                job['chapter_id'] = chapter_id
            if task:
                job['task_id'] = task['id']
            if answer is not None or images:
                if not isinstance(answer or '', str) or not ((answer or '').strip() or images):
                    raise OperationError('empty_answer', 'Enter your reasoning or answer first')
                job['answer'] = answer or ''
                if images:
                    job['images'] = list(images)
            if action == 'ask':
                if not isinstance(question, str) or not question.strip():
                    raise OperationError('empty_question', 'Enter your question first')
                job['question'] = question
                if images:
                    job['images'] = list(images)
            self.operation({'op': 'practice.job', 'job': job})
            return self.host.start_turn({'id': identifier, 'concept_id': concept_id, 'channel': 'practice',
                                         'record_user': False, 'prompt': prompts.PRACTICE_REQUEST})

    def generate(self, concept_id):
        # Retrieval questions (ADR 0008) and a chapter's quiz anchored here are not the section's own exercises.
        existing = [t for t in self.state()['tasks'] if t['concept_id'] == concept_id and t['origin'] not in RETRIEVAL_ORIGINS
                    and not chapter_owned(t) and t['status'] != 'replaced']
        if existing:
            return {'tasks': existing}
        return self._launch(concept_id, 'generate')

    def replace(self, concept_id, note=None):
        """Ask for different exercises (ADR 0011): new ones replace the section's untouched exercises the teacher wrote,
        once they are written. With none to replace, the new ones are added."""
        replaces = [t['id'] for t in self.state()['tasks'] if t['concept_id'] == concept_id and practice.replaceable(t) and not chapter_owned(t)]
        return self._launch(concept_id, 'generate', request={**({'replaces': replaces} if replaces else {}), **self._note(note)})

    def variant(self, task, note=None):
        """Another like this: one more exercise of the same kind next to it, replacing nothing (ADR 0011)."""
        if not practice.section_exercise(task):
            raise OperationError('invalid_action', 'Only a section exercise has variants')
        return self._launch(task['concept_id'], 'generate', request={'variant_of': task['id'], **self._note(note)})

    @staticmethod
    def _note(note):
        if note is not None and not isinstance(note, str):
            raise OperationError('invalid_request', 'note must be text')
        return {'note': note.strip()} if note and note.strip() else {}

    def act(self, task_id, action, answer=None, question=None, reason=None, images=None, note=None):
        task = next((t for t in self.state()['tasks'] if t['id'] == task_id), None)
        if not task:
            raise OperationError('unknown_exercise', 'Unknown exercise')
        if action == 'variant':
            return self.variant(task, note)
        if action not in self.ACTIONS:
            raise OperationError('invalid_action', 'Unknown practice action')
        if task.get('kind') == 'recall':
            raise OperationError('invalid_action', 'A recall question is answered by choosing an option')
        if action == 'defer' and task['origin'] == 'review':
            raise OperationError('invalid_action', 'A review question is not set aside; it can simply stay unanswered')
        if action == 'defer' and task['origin'] == 'chapter_quiz':
            raise OperationError('invalid_action', 'A chapter quiz question is optional; leave it unanswered instead of setting it aside')
        if action == 'skip':
            practice.require_skippable(task)
        if action in ('defer', 'skip'):
            with self.host.lock:
                # Setting the exercise aside cancels a request still running for it, so no late assessment reopens it.
                for job in self.state()['jobs']:
                    if job.get('task_id') == task['id'] and not job.get('processed'):
                        try:
                            self.host.pause_turn(job['id'])
                        except OperationError as exc:
                            if exc.code != 'unknown_turn':
                                raise
                request = {'op': 'practice.' + action, 'id': task['id']}
                if action == 'skip' and reason is not None:
                    request['reason'] = reason
                result = self.operation(request)
                self.host.changed()
                return result
        if action != 'assess':
            answer = None
        if action not in ('assess', 'ask'):
            images = None
        return self._launch(self._assessed_section(task), action, task, answer,
                            question=question if action == 'ask' else None, images=images)

    def _assessed_section(self, task):
        """The section a task's help and assessment are recorded for: its own, or the first section a chapter quiz question
        tests, so evidence and retests land on that section (ADR 0008)."""
        tested = task.get('tests_concept_ids') or []
        if task['origin'] == 'chapter_quiz' and tested and tested[0] in self.operation({'op': 'curriculum.view'})['route']:
            return tested[0]
        return task['concept_id']

    def next_section(self, concept_id, request_id):
        with self.host.lock:
            current = self._guard_mainline()
            if current.get('concept_id') not in (None, concept_id):
                raise OperationError('stale_position', 'The current position has changed; refresh the page')
            target = self.operation({'op': 'curriculum.context', 'concept_id': concept_id})['next_concept_id']
            if not target:
                return {'finished': True}
            return self._enter(target, request_id)

    def _guard_mainline(self):
        session = self.operation({'op': 'session.resume'})
        if session.get('active_branch') or any(b.get('choice') == 'accept' and not b.get('returned') for b in self.host.questions.list()):
            raise OperationError('active_branch', 'Return to the teaching mainline first')
        return session.get('position') or {}

    def _enter(self, concept_id, request_id):
        left = (self.operation({'op': 'course.status'})['position'] or {}).get('concept_id')
        self.host.navigation.discard_prepared()
        for turn in self.host.brief_turns():
            if turn['channel'] == 'mainline' and turn['status'] == 'running':
                self.host.pause_turn(turn['id'])
        concept = self.operation({'op': 'curriculum.context', 'concept_id': concept_id})['concept']
        chinese = self.operation({'op': 'preferences.view'})['preferences']['language'] == 'zh-CN'
        result = self.operation({'op': 'mainline.enter', 'request_id': request_id, 'concept_id': concept_id,
                                 'goal': prompts.section_goal(concept, chinese), 'next_step': '开始本小节讲解' if chinese else 'Begin teaching this section', 'progress': ''})
        if left and left != concept_id:
            self.host.memory.consolidate(left)
        self.host.changed()
        return result

    def skipped(self):
        """Sections the learner skipped, with their chapter or by jumping past them, and has not studied since."""
        deferred = self.operation({'op': 'evidence.unresolved'})['deferred']
        return [d for d in deferred if d['id'].startswith(review.SKIP_PREFIXES)]

    def skip_chapter(self, chapter_id, request_id):
        """Move on to the next chapter; the skipped sections stay on the route as deferred."""
        with self.host.lock:
            position = self._guard_mainline()
            model = self.operation({'op': 'curriculum.view'})
            chapter = next((c for c in model['chapters'] if c['id'] == chapter_id), None)
            current = position.get('concept_id') or next(iter(model['route']), None)
            if not chapter or current not in chapter['concept_ids']:
                raise OperationError('stale_position', 'Skip the chapter you are studying; refresh the page')
            end = model['route'].index(chapter['concept_ids'][-1])
            if end + 1 >= len(model['route']):
                raise OperationError('no_next_chapter', 'No later chapter is built yet')
            target = model['route'][end + 1]
            for cid in chapter['concept_ids'][chapter['concept_ids'].index(current):]:
                self.operation({'op': 'evidence.defer', 'id': f'chapter-skip:{chapter_id}:{cid}', 'concept_id': cid,
                                'reason': 'Learner skipped the chapter', 'section_id': chapter_id, 'target_concept_id': target})
            return self._enter(target, request_id)

    def jump(self, concept_id, request_id):
        """Study a later section now. The sections passed over that have no finished lesson, the current one included, stay on
        the route as skipped, like a skipped chapter's, deferred to the section jumped to (ADR 0006)."""
        with self.host.lock:
            position = self._guard_mainline()
            model = self.operation({'op': 'curriculum.view'})
            route = model['route']
            current = position.get('concept_id') or next(iter(route), None)
            if concept_id not in route:
                raise OperationError('unknown_concept', 'That section is not on the route')
            start, end = route.index(current), route.index(concept_id)
            if end <= start:
                # A retried jump finds the position already moved; any other earlier section is studied out of order
                # only once skipped.
                if concept_id == current:
                    return self._enter(concept_id, request_id)
                raise OperationError('not_ahead', 'Only a later section can be jumped to')
            studied = {t['concept_id'] for t in self.host.brief_turns()
                       if t['channel'] == 'mainline' and t['status'] == 'completed' and not t.get('chapter_id')}
            chapters = {cid: c['id'] for c in model['chapters'] for cid in c['concept_ids']}
            for cid in route[start:end]:
                if cid in studied:
                    continue
                self.operation({'op': 'evidence.defer', 'id': f'route-skip:{request_id}:{cid}', 'concept_id': cid,
                                'reason': 'Learner jumped to a later section', 'section_id': chapters.get(cid, cid),
                                'target_concept_id': concept_id})
            return self._enter(concept_id, request_id)

    def enter_skipped(self, concept_id, request_id):
        with self.host.lock:
            self._guard_mainline()
            if not any(d['concept_id'] == concept_id for d in self.skipped()):
                raise OperationError('not_skipped', 'Only a skipped section can be studied out of route order')
            return self._enter(concept_id, request_id)

    def resolve_skip(self, turn):
        if not turn.get('record_user'):
            return
        for item in self.skipped():
            if item['concept_id'] == turn['concept_id']:
                try:
                    self.operation({'op': 'evidence.resolve', 'id': 'resolved:' + item['id'], 'deferred_id': item['id'],
                                    'interaction_id': 'stream-user:' + turn['id']})
                except OperationError:
                    continue

    def _sources(self, refs):
        return self.operation({'op': 'source.units', 'refs': refs})['sources']

    def prompt(self, turn, context):
        state = self.operation({'op': 'practice.list'})
        job = next((j for j in state['jobs'] if j['id'] == turn['id']), None)
        if not job:
            return ''
        if job.get('purpose'):
            return self._retrieval_prompt(job, context, state['tasks'])
        if job['action'] == 'generate':
            # Exercise refs need not be included in the lesson links.
            sources = self._sources(context['concept'].get('exercises', []))
            if not {'note', 'replaces', 'variant_of'} & set(job):
                return prompts.practice_generate(sources)
            tasks = {t['id']: t for t in state['tasks']}
            kept = [t['question'] for t in state['tasks'] if t['concept_id'] == job['concept_id'] and practice.section_exercise(t)
                    and t['status'] not in ('replaced', 'skipped') and t['id'] not in job.get('replaces', [])]
            return prompts.different_exercises(sources, job.get('note'), [tasks[i]['question'] for i in job.get('replaces', []) if i in tasks],
                                               kept, tasks.get(job.get('variant_of'), {}).get('question'))
        task = next(t for t in state['tasks'] if t['id'] == job['task_id'])
        if job['action'] == 'ask':
            return prompts.practice_ask(task, self._sources(task['source_refs']), job['question'], len(job.get('images', [])))
        return prompts.practice_feedback(job['action'], task, self._sources(task['source_refs']), job.get('answer'), len(job.get('images', [])))

    def _retrieval_prompt(self, job, context, tasks):
        titles = {c['id']: c['title'] for c in self.operation({'op': 'curriculum.view'})['concepts']}
        if job['purpose'] == 'review':
            value = next((s for s in self.operation({'op': 'review.sets'})['sets'] if s['id'] == job.get('set_id')), {})
            found = self.operation({'op': 'review.context', 'set_id': job.get('set_id')})
            # Source excerpts keep a narrow review close to what was taught; a wide one relies on the lesson plans.
            excerpts = []
            if len(found['sections']) <= prompts.REVIEW_EXCERPT_SECTIONS:
                concepts = {c['id']: c for c in self.operation({'op': 'curriculum.view'})['concepts']}
                for section in found['sections']:
                    refs = concepts.get(section['id'], {}).get('links', [])[:prompts.REVIEW_EXCERPT_UNITS]
                    text = '\n'.join((s['unit'].get('text') or '') for s in self._sources(refs)) if refs else ''
                    if text.strip():
                        excerpts.append({'section': section['id'], 'text': text[:prompts.REVIEW_EXCERPT_CHARS]})
            return prompts.review_set(value, found, excerpts)
        chapter = next((c for c in self.operation({'op': 'curriculum.view'})['chapters'] if c['id'] == job.get('chapter_id')), None) or context['chapter']
        tested = set(chapter['concept_ids'])
        earlier = {t['id']: t for t in tasks if t['id'] in job.get('earlier', [])}
        again = [{'section': titles.get(earlier[i]['concept_id'], earlier[i]['concept_id']), 'question': earlier[i]['question']}
                 for i in job.get('earlier', []) if i in earlier]
        seen = [t['question'] for t in tasks if t['id'] not in earlier and ({t['concept_id'], *t.get('tests_concept_ids', [])} & tested)]
        # New questions test only sections the learner has studied (and not skipped), however much of the chapter remains.
        sections = [{'id': cid, 'title': titles.get(cid, cid)} for cid in self.operation({'op': 'practice.quiz_sections', 'chapter_id': chapter['id']})['sections']]
        return prompts.chapter_quiz(chapter, sections, seen, again)

    def quiz(self, chapter_id):
        """A chapter quiz: a few earlier exercises from the chapter asked again plus two or three new questions spanning
        it (ADR 0008). Offered once any section has a lesson, wherever the learner is, and it never moves the position. A
        new quiz waits until every question of the chapter's earlier quizzes has been answered."""
        with self.host.lock:
            chapter = self.host.navigation.studied_chapter(chapter_id)
            if any(t.get('chapter_id') == chapter_id and t['origin'] == 'chapter_quiz' and not any(h.get('action') == 'assess' for h in t['history'])
                   for t in self.state()['tasks']):
                raise OperationError('quiz_open', 'Answer the questions of the current quiz before taking it again')
            return self._launch(chapter['concept_ids'][-1], 'generate', purpose='chapter_quiz', chapter_id=chapter_id)

    def on_complete(self, turn):
        self.operation({'op': 'practice.complete', 'id': turn['id']})
        # A chapter recap asks for nothing: the chapter quiz is taken on purpose from the chapter page.
        if turn['channel'] == 'mainline' and not self.host.closing and not is_recap(turn) and not self.host.navigation.steps_remain(turn):
            self.generate(turn['concept_id'])


class Memory(Feature):
    """Course memory (ADR 0010). Every teaching prompt carries it through the snapshot; a lesson, side-question answer or
    practice help ends with a memory note, which the host records once the turn completes. Leaving a section starts one
    small-model turn that merges duplicate entries and prunes cleared or stale ones."""

    def consolidate(self, concept_id):
        """Starts the consolidation of the section the learner left, once per section; never in the learner's way."""
        if not self.operation({'op': 'memory.view'})['entries']:
            return {'created': False}
        try:
            return self.host.start_turn({'id': 'consolidation-' + concept_id, 'concept_id': concept_id, 'channel': 'consolidation',
                                         'record_user': False, 'prompt': prompts.CONSOLIDATION_REQUEST})
        except OperationError:
            log.info('Memory consolidation of %s could not start', concept_id, exc_info=True)
            return {'created': False}

    def consolidation_prompt(self, turn):
        titles = {c['id']: c['title'] for c in self.operation({'op': 'curriculum.view'})['concepts']}
        entries = [{'id': e['id'], 'kind': e['kind'], 'status': e['status'], 'text': e['text'], 'section': titles.get(e['concept_id'], e['concept_id'])}
                   for e in self.operation({'op': 'memory.view'})['entries']]
        return prompts.memory_consolidation(titles.get(turn['concept_id'], turn['concept_id']), entries)

    def _job(self, turn):
        if turn['channel'] != 'practice':
            return None
        return self.practice_job(turn['id'])

    def prompt(self, turn, context):
        if turn['channel'] in ('mainline', PREPARED_STEP, 'sidequestion'):
            return prompts.memory_note(json_reply=False)
        job = self._job(turn)
        # A request for different exercises with the learner's note may suggest how they like to practise (ADR 0011).
        if job and (job['action'] != 'generate' or job.get('note')):
            return prompts.memory_note(json_reply=True)
        return prompts.MEMORY_USE if turn['channel'] in ('practice', 'preparation') else ''

    def on_complete(self, turn):
        if turn['channel'] == 'consolidation':
            try:
                self.operation({'op': 'memory.consolidate', 'turn_id': turn['id'], 'concept_id': turn['concept_id'], 'reply': parse_json(turn['final_text'])})
            except (ValueError, OperationError):
                log.info('Memory consolidation %s was refused; memory is unchanged', turn['id'], exc_info=True)
            return
        if turn['channel'] in ('mainline', 'sidequestion'):
            own = ['stream-user:' + turn['id'], 'stream:' + turn['id']]
            note = tagged_json(memory.NOTE, turn['final_text'])
        else:
            job = self._job(turn)
            if not job or (job['action'] == 'generate' and not job.get('note')) or job.get('error'):
                return
            own = [p + job['id'] for p in ('practice-question:', 'practice-answer:', 'practice-feedback:', 'practice-request:')]
            try:
                note = parse_json(turn['final_text']).get('memory')
            except (ValueError, AttributeError):
                note = None
        if not isinstance(note, dict):
            return
        try:
            self.operation({'op': 'memory.note', 'turn_id': turn['id'], 'concept_id': turn['concept_id'], 'interaction_ids': own, 'note': note})
        except OperationError:
            log.info('Memory note of turn %s was refused', turn['id'], exc_info=True)


class Preparation(Feature):
    """Prepares the next section only while the learner's own work is idle."""
    INTERVAL = 2  # seconds between checks when nothing wakes the loop
    START_DELAY = .5
    MAX_BACKOFF = 60

    def __init__(self, host):
        super().__init__(host)
        self.operation({'op': 'preparation.recover'})
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='preparation')
        self._last = None

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def wake(self):
        """Something changed (a turn ended or paused, or the position moved): look for idle work now."""
        self._wake.set()

    def join(self, timeout):
        if self._thread.is_alive():
            self._thread.join(timeout)

    def state(self, concept_id=None):
        request = {'op': 'preparation.view'}
        if concept_id:
            request['concept_id'] = concept_id
        return self.operation(request)

    def before_start(self, request):
        # A chapter build runs alongside preparation; only the learner's own requests go first.
        if request.get('channel', 'mainline') in BACKGROUND:
            return
        for turn in self.host.brief_turns():
            if turn['channel'] == 'preparation' and turn['status'] == 'running':
                self.host.pause_turn(turn['id'])
        self.operation({'op': 'preparation.reconcile', 'brief': True})

    def prompt(self, turn, context):
        if turn['channel'] == 'preparation':
            job = next(j for j in self.state()['jobs'] if j['id'] == turn['id'])
            return prompts.preparation_task(job['snapshot']['context'])
        material = self.state(turn['concept_id'])['ready']
        if material and material['snapshot'].get('language', 'en') != turn.get('language', 'en'):
            material = None
        return prompts.preparation_material(material['content']) if material else prompts.PREPARATION_MISSING

    def schedule(self, retry=False):
        with self.host.lock:
            if self.host.closing:
                return {'scheduled': False, 'reason': 'host_closing'}
            stale = {j['id'] for j in self.state()['jobs'] if j['status'] == 'stale'}
            for turn in self.host.brief_turns():
                if turn['id'] in stale and turn['status'] == 'running':
                    self.host.pause_turn(turn['id'])
            turns = self.host.brief_turns()
            # A paused process can still be shutting down; never start a second preparation process.
            if any(t['status'] == 'running' and t['channel'] != 'build' for t in turns) or any(t['channel'] == 'preparation' and self.host.worker_alive(t) for t in turns):
                return {'scheduled': False, 'reason': 'foreground_or_worker_active'}
            values = self.state()
            concept_id = values['next_concept_id']
            if not concept_id:
                return {'scheduled': False, 'reason': 'no_next_section'}
            language = self.operation({'op': 'preferences.view'})['preferences']['language']
            relevant = [j for j in values['jobs'] if j['concept_id'] == concept_id and j['snapshot'].get('language', 'en') == language]
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
                                             'language': result['job']['snapshot']['language'], 'record_user': False, 'prompt': prompts.PREPARATION_REQUEST})
            except Exception:
                self.operation({'op': 'preparation.recover'})
                raise

    def _loop(self):
        # Host events wake the loop; the interval only catches changes made outside the host, such as Codex editing the route.
        # The first check waits briefly, so a lesson requested as the course opens goes first.
        failures = 0
        self._stop.wait(self.START_DELAY)
        self._wake.set()
        while not self._stop.is_set():
            self._wake.wait(min(self.INTERVAL * 2 ** failures, self.MAX_BACKOFF))
            self._wake.clear()
            if self._stop.is_set() or self.host.closing:
                return
            try:
                result = self.schedule()
                # With nothing to prepare and nothing running, write the Review for me set ahead (ADR 0014).
                if result.get('reason') in ('no_next_section', 'ready', 'failed', 'existing') and self.host.review.ahead:
                    self.host.review.prepare()
                summary = [(j['id'], j['status']) for j in self.state()['jobs']]
                if summary != self._last:
                    self._last = summary
                    # Publish directly: host.changed() would wake this loop again.
                    self.host.events.publish({'type': 'changed', 'scope': 'preparation'})
                failures = 0
            except OperationError:
                # Invalid or changing course sources never block the teacher.
                continue
            except Exception:
                if self.host.closing:
                    return
                failures += 1
                log.exception('Preparation scheduling failed; retrying')
