"""Builds a course the way a learner leaves it and saves it as tests/fixtures/courses/format-<N>.sql (ADR 0007).

Each stored format keeps one such fixture, written by the code of that format, and tests/test_course_fixtures.py opens
every fixture with the current code. Run this when a change adds a migration, after the migration, and commit the file:

    .venv/bin/python -m tests.fixtures.make_course

The course is studied through the HTTP host with a scripted teacher, as the interface would drive it: a course built as
the skill builds one, a stepped lesson with a check question, a side question with a follow-up, notes, exercises with
help and an assessment, a deferred exercise, a second section, a chapter recap and quiz, a review set, course memory and
background preparation. Paths inside the course folder are stored as `@COURSE@`, which the test replaces.
"""
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

from guided_learning import migrations
from guided_learning.api import execute
from tests.support import host_client, settle

PLACEHOLDER = '@COURSE@'
OUT = Path(__file__).resolve().parent / 'courses'

NOTES = '''# Superposition
Two paths reach the same detector, each with a complex amplitude.
The total amplitude is the sum of the path amplitudes.
The probability is the squared magnitude of the total amplitude.
# States
A state is a normalized vector; a global phase changes no probability.
# Measurement
A measurement in a basis gives each outcome with the squared magnitude of its component.
'''


def memory(*entries):
    return '\n<course-memory>' + json.dumps({'entries': [{'kind': k, 'text': t} for k, t in entries], 'cleared': []}) + '</course-memory>'


def check(question, right, wrong):
    return {'idea': question, 'question': question, 'correct': 0,
            'options': [{'text': right[0], 'explanation': right[1]}, {'text': wrong[0], 'explanation': wrong[1]}]}


STEPS = {
    1: ('## Path amplitudes\n\nEach path carries a complex amplitude $a$ or $b$.',
        {'title': 'Path amplitudes', 'remaining': [{'title': 'Adding amplitudes'}],
         'check': check('What does a path carry?', ('A complex amplitude', 'Each path contributes an amplitude.'),
                        ('A probability', 'Probabilities come only after adding.'))},
        memory(('taught_term', 'amplitude'), ('preference', 'Short steps with one formula each'))),
    2: ('## Adding amplitudes\n\n$$P = |a + b|^2 = |a|^2 + |b|^2 + 2\\,\\mathrm{Re}(a^* b)$$',
        {'remaining': []}, memory(('taught_term', 'interference term'))),
}


class Teacher:
    """Answers every kind of request the host makes, as the teacher would. The first section is taught in `steps`;
    later lessons are one step."""

    def __init__(self):
        self.steps = STEPS

    def run(self, prompt, cwd, emit, cancel, images=None):
        if 'Practice only (review set)' in prompt:
            text = json.dumps({'questions': [
                {'kind': 'recall', 'idea': 'global phase', 'question': 'Does a global phase change a probability?', 'tests_concept_ids': ['paths'],
                 'options': [{'text': 'No', 'explanation': 'Probabilities are squared magnitudes.'}, {'text': 'Yes', 'explanation': 'A common slip.'}],
                 'correct': 0},
                {'kind': 'apply', 'question': 'Three paths with equal amplitudes: when is the detector dark?', 'tests_concept_ids': ['paths', 'states']}]})
        elif 'Practice only (chapter quiz)' in prompt:
            text = json.dumps({'questions': [{'question': 'Connect interference and normalization.', 'tests_concept_ids': ['paths', 'states']}]})
        elif 'Practice only: return JSON {"questions"' in prompt:
            text = json.dumps({'questions': [{'question': 'Two paths have amplitudes $1/2$ and $e^{i\\phi}/2$.',
                                              'parts': [{'label': '(a)', 'text': 'Find $P(\\phi)$.'}, {'label': '(b)', 'text': 'When is it zero?'}],
                                              'origin': 'self_created', 'source_refs': []}]})
        elif 'Assess the reasoning' in prompt:
            count = int(re.search(r'with exactly (\d+) part', prompt)[1])
            text = json.dumps({'feedback': 'Part (a) is right; check the sign in (b).', 'parts': (['correct', 'not_yet'] * count)[:count],
                               'memory': {'entries': [{'kind': 'difficulty', 'text': 'Signs of phases'}]}})
        elif 'Practice only: return JSON {"feedback"' in prompt:
            text = json.dumps({'feedback': 'Expand $|z|^2 = z^* z$ first.'})
        elif 'Branch decision protocol' in prompt:
            text = ('Because $|z|^2 = z^* z$, the cross terms give $2\\,\\mathrm{Re}(a^* b)$.\n<teaching-decision>'
                    + json.dumps({'depth': 'short', 'category': 'local', 'rationale': 'Local algebra', 'suggest_supplement': False, 'supplement_goal': ''})
                    + '</teaching-decision>' + memory(('taught_term', 'complex conjugate')))
        elif 'Internal preparation task' in prompt:
            text = 'Prepared: measurement outcomes follow from squared components. Uncertain: none.'
        elif 'Consolidate the course memory' in prompt:
            text = json.dumps({'merge': [], 'prune': []})
        else:
            step = re.search(r'This reply teaches step (\d+)', prompt)
            if step and int(step[1]) in self.steps:
                body, block, remembered = self.steps[int(step[1])]
                text = body + remembered + '\n<lesson-step>' + json.dumps(block) + '</lesson-step>'
            else:
                text = '## Lesson\n\nA state is a normalized vector.\n<lesson-step>{"remaining": []}</lesson-step>'
        emit({'kind': 'delta', 'text': text[:20]})
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


def build(course):
    """The course as the skill builds it (course-operations.md)."""
    def op(**request):
        return execute(course, request)
    op(op='course.init', title='Introductory Quantum Mechanics')
    op(op='course.profile.save', profile={'goal': 'Understand interference and measurement', 'depth': 'standard',
                                          'prerequisites': [{'topic': 'Complex numbers', 'level': 'some', 'check': 'Multiplied two complex numbers'}],
                                          'focus': 'Problem solving'})
    op(op='memory.save', id='intake-1', kind='preference', text='Worked example before each new idea')
    op(op='memory.confirm', id='intake-1')
    op(op='widgets.save', ids=['plot'])
    notes = course / 'inputs' / 'notes.md'
    notes.parent.mkdir(parents=True)
    notes.write_text(NOTES, encoding='utf-8')
    source = op(op='source.register', path=str(notes))['source']
    ref = lambda line: {'source_id': source['id'], 'revision': source['revision'], 'unit_id': f'line-{line}'}
    op(op='curriculum.outline', chapters=[{'id': 'superposition', 'title': 'Superposition'}, {'id': 'measurement', 'title': 'Measurement'}])
    op(op='curriculum.chapter.save', chapter_id='superposition', concepts=[
        {'id': 'paths', 'title': 'Adding path amplitudes', 'objective': 'Predict interference from two amplitudes', 'links': [ref(2), ref(3), ref(4)],
         'exercises': [{**ref(4), 'question': 'Find the probability for equal amplitudes.', 'required_concepts': ['paths']}]},
        {'id': 'states', 'title': 'States and global phase', 'prerequisites': ['paths'], 'links': [ref(6)]}])
    op(op='curriculum.chapter.save', chapter_id='measurement', concepts=[
        {'id': 'outcomes', 'title': 'Measurement outcomes', 'prerequisites': ['states'], 'links': [ref(8)]}])
    op(op='mainline.enter', request_id='enter', concept_id='paths', goal='Predict interference', next_step='Start the lesson')


def study(course):
    """A learner's first two sections, through the HTTP host."""
    teacher = Teacher()
    client, host = host_client(course, runner=teacher)
    with client:
        def call(method, path, body=None):
            response = client.request(method, path, json=body)
            assert response.status_code == 200, (path, response.text)
            settle(host)
            return response.json()

        state = lambda: call('GET', '/api/state')
        # A stepped lesson: step 1 with a check question, answered, then Continue reveals the prepared step 2.
        call('POST', '/api/lessons', {})
        [lesson] = state()['lessons']
        first = lesson['steps'][0]['turn_id']
        call('POST', f'/api/lessons/{lesson["id"]}/steps/{first}/check', {'choice': 0})
        second = call('POST', f'/api/lessons/{lesson["id"]}/steps', {})['turn']['id']
        # A side question about a passage of step 1, and a follow-up.
        call('POST', '/api/questions', {'id': 'cross-term', 'question': 'Why is the cross term 2 Re(a* b)?', 'selection': 'a complex amplitude',
                                        'selected_turn_id': first, 'main_turn_id': second, 'anchor': {'scroll_y': 240}})
        call('POST', '/api/questions/cross-term/replies', {'question': 'And when both amplitudes are real?'})
        # Notes: a highlight, a note on a passage and a bookmark.
        call('POST', '/api/annotations', {'kind': 'highlight', 'concept_id': 'paths', 'turn_id': first, 'passage': 'complex amplitude', 'occurrence': 0})
        call('POST', '/api/annotations', {'kind': 'note', 'concept_id': 'paths', 'turn_id': first, 'passage': 'Each path', 'occurrence': 0,
                                          'note': 'Compare with classical intensities.'})
        call('POST', '/api/annotations', {'kind': 'bookmark', 'concept_id': 'paths'})
        # The exercise written after the last step: a hint, then an answer assessed by part.
        [task] = [t for t in state()['practice']['tasks'] if t['concept_id'] == 'paths']
        call('POST', f'/api/practice/tasks/{task["id"]}/hint', {'answer': ''})
        call('POST', f'/api/practice/tasks/{task["id"]}/assess', {'answer': '(a) P = (1 + cos phi)/2. (b) phi = 0.'})
        # A preference the teacher suggested, confirmed.
        suggested = next(e for e in state()['memory'] if e['kind'] == 'preference' and e['status'] == 'suggested')
        call('POST', f'/api/memory/{suggested["id"]}/confirm')

        # The next section: a one-step lesson, its exercise kept for later.
        teacher.steps = {}
        call('POST', '/api/sections/next', {'concept_id': 'paths', 'request_id': 'next-1'})
        call('POST', '/api/lessons', {})
        [task] = [t for t in state()['practice']['tasks'] if t['concept_id'] == 'states']
        call('POST', f'/api/practice/tasks/{task["id"]}/defer', {})

        # The chapter's recap and quiz, then a review set: a recall question answered and an apply question assessed.
        call('POST', '/api/chapters/superposition/recap', {})
        call('POST', '/api/chapters/superposition/quiz')
        review = call('POST', '/api/review/sets', {})['set']
        tasks = [t for t in state()['review']['tasks'] if t['set_id'] == review['id']]
        recall = next(t for t in tasks if t['kind'] == 'recall')
        call('POST', f'/api/review/tasks/{recall["id"]}/answer', {'choice': recall['correct']})
        apply = next(t for t in tasks if t['kind'] == 'apply')
        call('POST', f'/api/practice/tasks/{apply["id"]}/assess', {'answer': 'When the phases are 2 pi / 3 apart.'})

        # Background preparation of the next section, while the learner reads.
        host._wake_background()
        for _ in range(100):
            if any(j['status'] == 'ready' for j in state()['preparation']['jobs']):
                break
            settle(host)
        else:
            raise AssertionError('the next section was never prepared')


def dump(course):
    db = sqlite3.connect(course / 'course.sqlite3')
    try:
        sql = '\n'.join(db.iterdump()) + '\n'
    finally:
        db.close()
    for form in {str(course), json.dumps(str(course))[1:-1]}:
        sql = sql.replace(form, PLACEHOLDER)
    for machine in {str(Path.home()), tempfile.gettempdir(), str(Path(tempfile.gettempdir()).resolve())}:
        if machine in sql:
            raise AssertionError(f'{machine} is stored in the course; make it a placeholder')
    return sql


def main():
    with tempfile.TemporaryDirectory() as scratch:
        course = Path(scratch).resolve() / 'quantum'
        build(course)
        study(course)
        sql = dump(course)
    version = re.search(r'"version": (\d+)', next(line for line in sql.splitlines() if "'course','schema'" in line))[1]
    assert int(version) == migrations.VERSION, version
    OUT.mkdir(exist_ok=True)
    target = OUT / f'format-{migrations.VERSION}.sql'
    target.write_text(sql, encoding='utf-8')
    print(target)


if __name__ == '__main__':
    sys.exit(main())
