"""The skill's operations as a contract (docs/stability.md): the result fields the references document for Codex and
the error codes they name. Operations run on a copy of the newest fixture course, a course a learner has studied.

A result keeps every field it returned through 1.x, so each check lists the fields the result has now; a new field is
fine, a missing one is a 2.0 change. The operation names themselves are checked in test_stable_operations.py, the
course formats in test_course_fixtures.py and course packages in test_package_fixtures.py.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from throughline import migrations
from throughline.api import execute
from throughline.store import OperationError
from tests.sample_pdf import write_pdf
from tests.support import ROOT
from tests.test_course_fixtures import FIXTURES, load


def has_pdf_extra():
    try:
        import pypdf, pypdfium2, PIL  # noqa: F401
        return True
    except ImportError:
        return False


class Contract(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name).resolve()
        self.course = self.home / 'library' / 'quantum'
        load(FIXTURES / f'format-{migrations.VERSION}.sql', self.course)
        self.source = self.op('course.status')['sources'][0]
        self.ref = {'source_id': self.source['id'], 'revision': self.source['revision']}

    def op(self, op, **fields):
        return execute(self.course, {'op': op, **fields})

    def environment(self):
        """The command's environment, with the library and every per-user folder inside the test's own folder."""
        return {**os.environ, 'THROUGHLINE_HOME': str(self.home / 'library'), 'THROUGHLINE_SKILLS_DIR': str(self.home / '.skills'),
                'XDG_DATA_HOME': str(self.home / '.xdg'), 'APPDATA': str(self.home / '.appdata')}

    def refused(self, code, op, course=None, **fields):
        """The operation is refused with `code`, and changes nothing."""
        course = course or self.course
        before = self.snapshot(course)
        with self.assertRaises(OperationError) as refused:
            execute(course, {'op': op, **fields})
        self.assertEqual(refused.exception.code, code, str(refused.exception))
        self.assertEqual(self.snapshot(course), before, f'a refused {op} changes nothing')
        return refused.exception

    def snapshot(self, course):
        db = sqlite3.connect(course / 'course.sqlite3')
        try:
            return db.execute('SELECT namespace, key, value FROM documents ORDER BY namespace, key').fetchall()
        finally:
            db.close()

    def assertFields(self, value, fields, where=''):
        self.assertIsInstance(value, dict, where)
        self.assertEqual(sorted(set(fields) - set(value)), [], f'{where} keeps its fields: has {sorted(value)}')


class Results(Contract):
    def test_the_command_answers_in_an_envelope(self):
        """course-operations.md: exit 0 returns {ok: true, result}; exit 1 returns {ok: false, error: {code, message}}."""
        env = self.environment()

        def run(*args, request):
            return subprocess.run([sys.executable, '-m', 'throughline', *args], input=json.dumps(request), text=True, encoding='utf-8',
                                  capture_output=True, cwd=ROOT, env=env, timeout=60)
        for address in (('--workspace', str(self.course)), ('--course', 'quantum')):
            ok = run(*address, request={'op': 'course.status'})
            self.assertEqual(ok.returncode, 0, ok.stderr)
            response = json.loads(ok.stdout)
            self.assertEqual((response['ok'], response['result']['course']['title']), (True, 'Introductory Quantum Mechanics'))
            failed = run(*address, request={'op': 'widgets.save', 'ids': ['sparkles']})
            self.assertEqual(failed.returncode, 1)
            response = json.loads(failed.stdout)
            self.assertFalse(response['ok'])
            self.assertEqual(response['error']['code'], 'unknown_widget')
            self.assertTrue(response['error']['message'])
        request = self.home / 'request.json'
        request.write_text(json.dumps({'op': 'preferences.view'}), encoding='utf-8')
        from_file = run('--course', 'quantum', '--request', str(request), request={})
        self.assertEqual(json.loads(from_file.stdout)['result'], {'preferences': {'language': 'en'}})

    def test_course_status(self):
        status = self.op('course.status')
        self.assertFields(status, ('course', 'position', 'sources', 'profile'))
        self.assertFields(status['course'], ('id', 'title'))
        self.assertFields(status['position'], ('concept_id', 'goal', 'next_step', 'progress'))
        self.assertEqual(status['position']['concept_id'], 'states')
        self.assertFields(status['sources'][0], ('id', 'path', 'revision', 'status', 'verification', 'errors'), 'a source')
        self.assertFields(status['profile'], ('goal', 'depth', 'prerequisites', 'focus'))

    def test_course_writes(self):
        self.assertEqual(self.op('course.init', title='Something else')['course']['title'], 'Introductory Quantum Mechanics',
                         'reopening via init preserves the existing title')
        self.assertEqual(self.op('course.rename', title='Quantum mechanics II')['course']['title'], 'Quantum mechanics II')
        self.assertEqual(self.op('course.status')['course']['title'], 'Quantum mechanics II')
        self.assertEqual(self.course.name, 'quantum', 'the folder name stays')
        profile = {'goal': 'Pass the final', 'depth': 'rigorous', 'prerequisites': [{'topic': 'Eigenvalues', 'level': 'some', 'check': 'Found them for 2x2'}]}
        self.assertEqual(self.op('course.profile.save', profile=profile)['profile'], profile)
        self.assertEqual(self.op('course.status')['profile'], profile, 'replacing any earlier one')
        self.assertEqual(self.op('preferences.save', language='zh-CN'), {'preferences': {'language': 'zh-CN'}})
        self.assertEqual(self.op('preferences.view'), {'preferences': {'language': 'zh-CN'}})

    def test_course_memory(self):
        saved = self.op('memory.save', id='intake-9', kind='preference', text='Define each symbol before using it')['entry']
        self.assertFields(saved, ('id', 'kind', 'text', 'status', 'concept_id'))
        self.assertEqual((saved['id'], saved['kind'], saved['status'], saved['concept_id']), ('intake-9', 'preference', 'suggested', None))
        self.assertEqual(self.op('memory.confirm', id='intake-9')['entry']['status'], 'confirmed')

    def test_widgets(self):
        listed = self.op('widgets.list')
        self.assertFields(listed, ('library', 'selected'))
        self.assertEqual(listed['selected'], ['plot'])
        for widget in listed['library']:
            self.assertFields(widget, ('id', 'summary', 'subjects'), 'an add-on')
        self.assertTrue({'plot', 'chemistry', 'figure'} <= {w['id'] for w in listed['library']}, 'the add-ons the references name')
        self.assertEqual(self.op('widgets.save', ids=['chemistry', 'figure'])['selected'], ['chemistry', 'figure'])
        self.assertEqual(self.op('widgets.list')['selected'], ['chemistry', 'figure'], 'save replaces the add-ons')

    def test_cover(self):
        listed = self.op('cover.list')
        self.assertFields(listed, ('patterns', 'cover'))
        for pattern in listed['patterns']:
            self.assertFields(pattern, ('id', 'looks', 'subjects'), 'a pattern')
        self.assertTrue({'contours', 'waves', 'lattice', 'grid', 'orbits', 'field', 'branches', 'scatter', 'ruled'} <= {p['id'] for p in listed['patterns']},
                        'a pattern a course may have saved stays')
        self.assertEqual(self.op('cover.save', name='QM', pattern='orbits'), {'cover': {'name': 'QM', 'pattern': 'orbits'}})
        self.assertEqual(self.op('course.status')['cover'], {'name': 'QM', 'pattern': 'orbits'})

    def test_text_sources(self):
        read = self.op('source.read', source_id=self.source['id'])
        self.assertFields(read, ('source_id', 'revision', 'path', 'status', 'errors', 'verification', 'units'))
        self.assertEqual(read['units'][1], {'id': 'line-2', 'locator': {'line': 2}, 'text': 'Two paths reach the same detector, each with a complex amplitude.'})
        self.assertEqual(self.op('source.read', **self.ref)['revision'], self.source['revision'], 'an earlier revision by `revision`')
        found = self.op('source.search', query='detector')
        self.assertFields(found, ('units', 'more'))
        [unit] = found['units']
        self.assertFields(unit, ('source_id', 'revision', 'unit_id', 'path', 'locator', 'excerpt', 'matches'))
        self.assertEqual(unit['unit_id'], 'line-2')

        # Registering again after a change, a moved file, and a converted document.
        notes = self.course / 'inputs' / 'phases.md'
        notes.write_text('# Phases\nA global phase changes no probability.\n', encoding='utf-8')
        first = self.op('source.register', path=str(notes))['source']
        self.assertFields(first, ('id', 'path', 'revision', 'status', 'verification', 'errors'))
        self.assertEqual((first['path'], first['status']), (str(notes), 'read'))
        notes.write_text('# Phases\nA global phase changes no probability.\nA relative phase does.\n', encoding='utf-8')
        again = self.op('source.register', path=str(notes))['source']
        self.assertEqual(again['id'], first['id'], 'a source keeps its id across revisions')
        self.assertNotEqual(again['revision'], first['revision'])
        earlier = self.op('source.read', source_id=first['id'], revision=first['revision'])
        self.assertEqual(len(earlier['units']), 2, 'the earlier revision stays readable')
        moved = self.course / 'inputs' / 'notes' / 'phases.md'
        moved.parent.mkdir()
        shutil.move(notes, moved)
        taken = self.op('source.register', path=str(moved))
        self.assertEqual(taken['source']['id'], first['id'], 'a moved file keeps its source')
        self.assertEqual(taken['moved_from'], str(notes))
        original = self.course / 'inputs' / 'lecture.docx'
        original.write_bytes(b'a document')
        converted = self.course / 'inputs' / 'converted' / 'lecture.docx.md'
        converted.parent.mkdir()
        converted.write_text('# Lecture\nConverted text.\n', encoding='utf-8')
        source = self.op('source.register', path=str(converted), converted_from=str(original))['source']
        self.assertFields(source['converted_from'], ('path', 'revision'))
        self.assertEqual(source['converted_from']['path'], str(original))
        # A document that is neither PDF nor text, and a missing file, are recorded as failed registrations.
        refused = self.op('source.register', path=str(original))['source']
        self.assertEqual(refused['status'], 'failed')
        self.assertIn('convert to PDF', refused['errors'][0])
        missing = self.op('source.register', path=str(self.course / 'inputs' / 'gone.md'))['source']
        self.assertEqual((missing['status'], missing['revision']), ('failed', None))
        self.assertIn(missing['id'], [s['id'] for s in self.op('course.status')['sources']], 'a missing file stays visible')

    def test_curriculum_reads(self):
        model = self.op('curriculum.view')
        self.assertFields(model, ('concepts', 'route', 'chapters', 'coverage'))
        self.assertEqual(model['route'], ['paths', 'states', 'outcomes'])
        self.assertFields(model['chapters'][0], ('id', 'title', 'concept_ids'), 'a chapter')
        chapter = self.op('curriculum.chapter.view', chapter_id='superposition')
        self.assertFields(chapter, ('chapter', 'concepts', 'coverage'))
        self.assertEqual([c['id'] for c in chapter['concepts']], ['paths', 'states'])
        context = self.op('curriculum.context', concept_id='states')
        self.assertFields(context, ('concept', 'chapter', 'prerequisites', 'next_concept_id', 'position', 'sources'))
        self.assertEqual((context['chapter']['id'], context['chapter']['index'], context['chapter']['total']), ('superposition', 0, 2))
        self.assertEqual(([p['id'] for p in context['prerequisites']], context['next_concept_id']), (['paths'], 'outcomes'))
        self.assertEqual(self.op('curriculum.context')['concept']['id'], 'states', 'omitting the id reads the position')
        coverage = self.op('curriculum.coverage')
        self.assertFields(coverage, ('units', 'sources', 'stale_mappings', 'semantic_completeness'))
        self.assertFields(coverage['units'][0], ('source_id', 'revision', 'unit_id', 'locator', 'disposition', 'concept_ids', 'verification'), 'a unit')
        check = self.op('curriculum.check')
        self.assertEqual(check, {'violations': [], 'exercises': 1, 'without_required_concepts': 0})

    def test_curriculum_check_reports_an_exercise_placed_too_early(self):
        """A course saved before the placement rule may hold violations; the check names each one."""
        db = sqlite3.connect(self.course / 'course.sqlite3')
        [(value,)] = db.execute("SELECT value FROM documents WHERE namespace='curriculum' AND key='model'").fetchall()
        model = json.loads(value)
        paths = next(c for c in model['concepts'] if c['id'] == 'paths')
        paths['exercises'].append({**self.ref, 'unit_id': 'line-8', 'question': 'Predict the outcomes.', 'required_concepts': ['paths', 'outcomes', 'ghost']})
        paths['exercises'].append({**self.ref, 'unit_id': 'line-3', 'question': 'An old one.'})
        db.execute("UPDATE documents SET value=? WHERE namespace='curriculum' AND key='model'", (json.dumps(model),))
        db.commit()
        db.close()
        check = self.op('curriculum.check')
        self.assertEqual((check['exercises'], check['without_required_concepts']), (3, 1))
        [violation] = check['violations']
        self.assertFields(violation, ('concept_id', 'chapter_id', 'question', 'source_id', 'revision', 'unit_id', 'later_concepts', 'unknown_concepts', 'move_to'))
        self.assertEqual({k: violation[k] for k in ('concept_id', 'chapter_id', 'question', 'later_concepts', 'unknown_concepts', 'move_to')},
                         {'concept_id': 'paths', 'chapter_id': 'superposition', 'question': 'Predict the outcomes.', 'later_concepts': ['outcomes'],
                          'unknown_concepts': ['ghost'], 'move_to': 'outcomes'})

    def test_curriculum_writes(self):
        outlined = self.op('curriculum.outline', chapters=[{'id': 'superposition', 'title': 'Superposition'}, {'id': 'measurement', 'title': 'Measurement'},
                                                            {'id': 'dynamics', 'title': 'Dynamics', 'summary': 'How states change in time.'}])
        self.assertEqual([c['id'] for c in outlined['chapters']], ['superposition', 'measurement', 'dynamics'])
        self.op('curriculum.chapter.save', chapter_id='dynamics', concepts=[
            {'id': 'evolution', 'title': 'Time evolution', 'core_question': 'How does a state change?', 'objective': 'Evolve a state',
             'prerequisites': ['outcomes'], 'links': [{**self.ref, 'unit_id': 'line-6'}],
             'exercises': [{**self.ref, 'unit_id': 'line-8', 'question': '2(a)', 'required_concepts': ['evolution', 'outcomes'], 'part_of': '2',
                            'other_parts': [{'question': '2(b)'}]}]}])
        view = self.op('curriculum.chapter.view', chapter_id='dynamics')
        [concept] = view['concepts']
        self.assertEqual((concept['core_question'], concept['exercises'][0]['part_of']), ('How does a state change?', '2'))
        self.assertEqual(self.op('curriculum.view')['route'], ['paths', 'states', 'outcomes', 'evolution'])
        model = self.op('curriculum.view')
        saved = self.op('curriculum.save', concepts=model['concepts'], route=model['route'], coverage=model['coverage'])
        self.assertEqual([c['id'] for c in saved['chapters']], ['superposition', 'measurement', 'dynamics'], 'without chapters, the stored ones are kept')

    def test_checkpoints_replay(self):
        """course-operations.md: a retry returns replayed:true, the current position and the first response."""
        position = {'goal': 'Normalize', 'progress': 'Introduced density', 'next_step': 'Normalize the example'}
        first = self.op('position.save', request_id='checkpoint-1', position=position)
        self.assertEqual(first, {'position': position, 'replayed': False})
        entered = self.op('mainline.enter', request_id='enter-2', concept_id='outcomes', goal='Measure', next_step='Start')
        self.assertFields(entered, ('position', 'due_explanations', 'replayed'))
        self.assertEqual((entered['position']['concept_id'], entered['replayed']), ('outcomes', False))
        retry = self.op('position.save', request_id='checkpoint-1', position=position)
        self.assertEqual(retry['replayed'], True)
        self.assertEqual(retry['position'], entered['position'], 'the current position, never the old one')
        self.assertEqual(retry['original_result'], {'position': position})

    def test_streams_and_resume(self):
        turns = self.op('stream.summaries', brief=True)['turns']
        for turn in turns:
            self.assertFields(turn, ('id', 'concept_id', 'channel', 'status'), 'a turn')
        studied = {t['concept_id'] for t in turns if t['channel'] == 'mainline' and t['status'] == 'completed' and not t.get('chapter_id')}
        self.assertEqual(studied, {'paths', 'states'}, 'curriculum.md: how Codex finds the studied sections')
        self.assertEqual([t['chapter_id'] for t in turns if t.get('chapter_id')], ['superposition'], 'the chapter recap')
        resumed = self.op('session.resume')
        self.assertFields(resumed, ('position', 'context', 'active_branch', 'due_explanations', 'unanswered_questions', 'recent_interactions', 'app_questions'))

    def test_annotations(self):
        listed = self.op('annotations.list', concept_id='paths')['annotations']
        self.assertEqual([a['kind'] for a in listed], ['highlight', 'note', 'bookmark'], 'oldest first')
        for annotation in listed:
            self.assertFields(annotation, ('id', 'kind', 'concept_id', 'turn_id', 'task_id', 'source', 'passage', 'occurrence', 'note'), 'an annotation')
        turn = listed[0]['turn_id']
        saved = self.op('annotations.save', id='mine', kind='note', turn_id=turn, passage='complex amplitude', occurrence=0, note='Like phasors')['annotation']
        self.assertEqual((saved['id'], saved['note'], saved['passage']), ('mine', 'Like phasors', 'complex amplitude'))
        updated = self.op('annotations.save', id='mine', kind='note', turn_id=turn, passage='something else', note='Exactly phasors')['annotation']
        self.assertEqual((updated['note'], updated['passage']), ('Exactly phasors', 'complex amplitude'), 'an existing id only updates note')
        self.op('annotations.delete', id='mine')
        self.assertNotIn('mine', [a['id'] for a in self.op('annotations.list')['annotations']])

    def test_practice(self):
        listed = self.op('practice.list')
        self.assertFields(listed, ('tasks', 'jobs'))
        exercise = next(t for t in listed['tasks'] if t['concept_id'] == 'paths' and t['origin'] == 'self_created')
        self.assertFields(exercise, ('id', 'concept_id', 'question', 'parts', 'origin', 'source_refs', 'status', 'history'), 'an exercise')
        self.assertEqual(exercise['status'], 'attempted')
        assessed = next(h for h in exercise['history'] if h.get('action') == 'assess')
        self.assertEqual(assessed['parts'], ['correct', 'not_yet'], 'the assessed part statuses')
        self.assertEqual({t['origin'] for t in listed['tasks']} - {'self_created', 'source'}, {'review'})
        deferred = next(t for t in listed['tasks'] if t['concept_id'] == 'states')
        self.assertEqual(deferred['status'], 'deferred')

        course_exercise = {'question': 'Find the probability for equal amplitudes: $P = |a + b|^2$.', 'origin': 'source',
                           'source_refs': [{**self.ref, 'unit_id': 'line-4'}], 'exercise': 'Find the probability for equal amplitudes.'}
        request = {'id': 'ps3', 'concept_id': 'paths', 'exercises': [course_exercise, {'question': 'Two detectors', 'parts': ['(a) one', {'label': '(b)', 'text': 'two'}],
                                                                                         'origin': 'self_created'}]}
        added = self.op('practice.add', **request)['tasks']
        self.assertEqual([t['id'] for t in added], ['ps3:0', 'ps3:1'])
        self.assertFields(added[0], ('id', 'concept_id', 'question', 'origin', 'source_refs', 'status', 'history', 'exercise'), 'an added exercise')
        self.assertEqual(added[0]['status'], 'pending')
        self.assertEqual(self.op('practice.add', **request)['tasks'], added, 'a repeated request adds nothing')

        revised = self.op('practice.revise', id='ps3:1', question='Two detectors, one source')['task']
        self.assertEqual(revised['question'], 'Two detectors, one source')
        self.assertEqual(revised['revisions'][0]['question'], 'Two detectors', 'earlier wordings are kept')
        retired = self.op('practice.retire', id='ps3:1', reason='Duplicate of problem 2')['task']
        self.assertEqual(retired['status'], 'retired')
        kept = self.op('practice.revise', id=exercise['id'], question='Reworded', parts=['(a) again', '(b) again'])['task']
        self.assertEqual((kept['history'], kept['status']), (exercise['history'], 'attempted'), 'answers and help stay')


    def test_review_data_and_what_studio_writes(self):
        """What Studio reads of the learner's review and writes into the Review place (issue #229)."""
        mistakes = self.op('mistakes.list')
        self.assertFields(mistakes, ('entries',))
        for entry in mistakes['entries']:
            self.assertFields(entry, ('id', 'kind', 'concept_ids', 'question', 'missed_at', 'right_at'), 'a mistake')
        context = self.op('review.context', sections=['paths'])
        self.assertFields(context, ('sections', 'earlier'))
        self.assertFields(context['sections'][0], ('id', 'title', 'days_since_practised', 'recent_misses', 'set_aside'), 'a section')
        apply = {'kind': 'apply', 'question': 'Three paths: when is it dark?', 'parts': ['(a)', '(b)'], 'tests_concept_ids': ['paths'], 'marks': 4}
        written = self.op('drill.write', id='mock-1', title='Mock exam', exam=True, note='Twenty minutes.', questions=[apply], handoff_id='review:1')
        self.assertFields(written, ('session', 'task_ids'))
        self.assertFields(written['session'], ('id', 'title', 'created_at'), 'a written session')
        sessions = self.op('drill.list')['sessions']
        self.assertFields(next(s for s in sessions if s['id'] == 'mock-1'), ('id', 'kind', 'title', 'sections', 'task_ids', 'created_at'), 'a session')
        task = next(t for t in self.op('practice.list')['tasks'] if t['id'] == written['task_ids'][0])
        self.assertEqual((task['origin'], task['session_id'], task['marks']), ('review', 'mock-1', 4))
        sheet = self.op('sheet.save', id='formulas', title='Formula sheet', markdown='$P = |a + b|^2$', scope={'concept_ids': ['paths']})
        self.assertFields(sheet['sheet'], ('id', 'title', 'markdown', 'scope', 'created_at', 'updated_at'), 'a sheet')
        self.assertFields(self.op('sheet.list'), ('sheets',))

class Errors(Contract):
    """Each error code the references name, triggered the way they describe."""

    def test_invalid_request(self):
        ref = {**self.ref, 'unit_id': 'line-4'}
        self.refused('invalid_request', 'curriculum.chapter.save', chapter_id='superposition', concepts=[
            {'id': 'paths', 'title': 'Paths', 'exercises': [{**ref, 'question': 'Find P.'}]}, {'id': 'states', 'title': 'States', 'prerequisites': ['paths']}])
        self.refused('invalid_request', 'position.save', position={'goal': 'No id'})
        self.refused('invalid_request', 'mainline.enter', concept_id='states', goal='g', next_step='n')
        converted = self.course / 'inputs' / 'slides.md'
        converted.write_text('Slides', encoding='utf-8')
        self.refused('invalid_request', 'source.register', path=str(converted), converted_from=str(self.course / 'inputs' / 'missing.pptx'))
        self.refused('invalid_request', 'source.readings.save', **self.ref, readings=[{'page': 1, 'text': 'A text source is exact'}])

    def test_curriculum_errors(self):
        ref = {**self.ref, 'unit_id': 'line-4'}
        self.refused('exercise_placement', 'curriculum.chapter.save', chapter_id='superposition', concepts=[
            {'id': 'paths', 'title': 'Paths', 'exercises': [{**ref, 'question': 'Find P.', 'required_concepts': ['paths', 'outcomes']}]},
            {'id': 'states', 'title': 'States', 'prerequisites': ['paths']}])
        self.refused('invalid_reference', 'curriculum.chapter.save', chapter_id='superposition', concepts=[
            {'id': 'paths', 'title': 'Paths', 'prerequisites': ['ghost']}, {'id': 'states', 'title': 'States'}])
        self.refused('invalid_reference', 'curriculum.chapter.save', chapter_id='superposition', concepts=[
            {'id': 'paths', 'title': 'Paths', 'links': [{**self.ref, 'unit_id': 'line-99'}]}, {'id': 'states', 'title': 'States', 'prerequisites': ['paths']}])
        self.refused('invalid_chapters', 'curriculum.outline', chapters=[{'id': 'measurement', 'title': 'Measurement'}])
        self.refused('invalid_route', 'curriculum.outline', chapters=[{'id': 'measurement', 'title': 'Measurement'}, {'id': 'superposition', 'title': 'Superposition'}])
        model = self.op('curriculum.view')
        cyclic = [{**c, 'prerequisites': ['outcomes']} if c['id'] == 'paths' else c for c in model['concepts']]
        self.refused('prerequisite_cycle', 'curriculum.save', concepts=cyclic, route=model['route'], coverage=model['coverage'])

    def test_reordering_needs_the_learners_agreement(self):
        course = self.home / 'flat'
        execute(course, {'op': 'course.init', 'title': 'Flat'})
        concepts = [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B'}]
        execute(course, {'op': 'curriculum.save', 'concepts': concepts, 'route': ['a', 'b'], 'coverage': []})
        self.refused('confirmation_required', 'curriculum.save', course=course, concepts=concepts, route=['b', 'a'], coverage=[])
        saved = execute(course, {'op': 'curriculum.save', 'concepts': concepts, 'route': ['b', 'a'], 'coverage': [], 'confirm_reorder': True})
        self.assertEqual(saved['route'], ['b', 'a'])
        self.assertEqual([(c['id'], c['concept_ids']) for c in saved['chapters']], [('course', ['b', 'a'])], 'a flat route is one chapter, id `course`')

    def test_checkpoint_conflict(self):
        self.op('position.save', request_id='checkpoint-1', position={'goal': 'First'})
        self.refused('id_conflict', 'position.save', request_id='checkpoint-1', position={'goal': 'Changed'})

    def test_practice_errors(self):
        exercise = {'question': 'Find the probability for equal amplitudes.', 'origin': 'source', 'source_refs': [{**self.ref, 'unit_id': 'line-4'}],
                    'exercise': 'Find the probability for equal amplitudes.'}
        self.op('practice.add', id='ps3', concept_id='paths', exercises=[exercise])
        self.refused('exercise_exists', 'practice.add', id='ps4', concept_id='paths', exercises=[exercise])
        answered = next(t for t in self.op('practice.list')['tasks'] if t['concept_id'] == 'paths' and t['origin'] == 'self_created')
        self.refused('exercise_answered', 'practice.revise', id=answered['id'], parts=['(a) only one part now'])
        self.refused('exercise_answered', 'practice.retire', id=answered['id'], reason='Duplicate')

    def test_review_errors(self):
        apply = {'kind': 'apply', 'question': 'Three paths: when is it dark?', 'tests_concept_ids': ['paths']}
        self.refused('nothing_to_review', 'drill.write', id='m', title='Measurement', scope={'chapter_ids': ['measurement']}, questions=[{**apply, 'tests_concept_ids': ['outcomes']}])
        self.refused('invalid_review_question', 'drill.write', id='m', title='T', questions=[apply] * 31)
        self.refused('invalid_review_question', 'drill.write', id='m', title='T', questions=[
            apply, {'kind': 'recall', 'question': 'One option?', 'tests_concept_ids': ['paths'], 'options': [{'text': 'Yes', 'explanation': 'Only one.'}], 'correct': 0}])
        self.refused('unknown_concept', 'sheet.save', id='s', title='T', markdown='x', scope={'chapter_ids': ['nowhere']})

    def test_unknown_widget(self):
        self.refused('unknown_widget', 'widgets.save', ids=['plot', 'sparkles'])

    def test_cover_errors(self):
        self.refused('unknown_pattern', 'cover.save', name='QM', pattern='sparkles')
        self.refused('invalid_cover', 'cover.save', name='Introductory Quantum Mechanics', pattern='orbits')

    def test_a_newer_course_is_refused(self):
        db = sqlite3.connect(self.course / 'course.sqlite3')
        db.execute("UPDATE documents SET value=? WHERE namespace='course' AND key='schema'", (json.dumps({'version': migrations.VERSION + 1}),))
        db.commit()
        db.close()
        self.refused('course_too_new', 'course.status')
        self.refused('course_too_new', 'memory.save', id='x', kind='preference', text='Nothing is written')


@unittest.skipUnless(has_pdf_extra(), 'Install the pdf extra for page readings')
class PageReadings(Contract):
    FIGURE = {'label': 'Figure 1', 'caption': 'Two paths', 'description': 'Two beams from one source meet at a detector D.', 'box': [0.1, 0.2, 0.9, 0.6]}

    def setUp(self):
        super().setUp()
        pdf = self.course / 'inputs' / 'lecture.pdf'
        write_pdf(pdf, [['Interference of two paths'], ['A figure page'], ['Problems']])
        self.pdf = self.op('source.register', path=str(pdf))['source']
        self.pdf_ref = {'source_id': self.pdf['id'], 'revision': self.pdf['revision']}

    def test_reading_the_pages(self):
        status = next(s for s in self.op('course.status')['sources'] if s['id'] == self.pdf['id'])
        self.assertFields(status, ('pages', 'pages_read', 'problem_pages', 'verification'))
        self.assertEqual((status['pages'], status['pages_read'], status['verification']), (3, 0, 'pending'))
        rendered = self.op('source.render', source_id=self.pdf['id'], pages=[1, 2], size=400)
        self.assertEqual([i['page'] for i in rendered['images']], [1, 2])
        self.assertTrue(all(Path(i['path']).is_file() for i in rendered['images']))

        saved = self.op('source.readings.save', **self.pdf_ref, readings=[
            {'page': 1, 'text': 'Interference of two paths: $P = |a + b|^2$', 'figures': [], 'problems': []},
            {'page': 2, 'text': 'A figure page', 'figures': [self.FIGURE], 'problems': ['The bottom margin is cut off']}])
        self.assertFields(saved, ('saved', 'readings'))
        self.assertEqual(saved['saved'], [1, 2])
        self.assertEqual(saved['readings'], {'pages': 3, 'read': 2, 'unread': [[3, 3]], 'problems': [[2, 2]]})

        read = self.op('source.read', source_id=self.pdf['id'])
        self.assertEqual(read['readings'], saved['readings'])
        first, second, third = read['units']
        self.assertEqual((first['id'], first['locator'], first['reading'], first['verification']), ('page-1', {'page': 1}, True, 'verified'))
        self.assertEqual(first['text'], 'Interference of two paths: $P = |a + b|^2$')
        [figure] = second['figures']
        self.assertFields(figure, ('id', 'label', 'caption', 'description'))
        self.assertEqual(second['problems'], ['The bottom margin is cut off'])
        self.assertNotIn('reading', third)
        shown = self.op('source.figure', id=figure['id'])['figure']
        self.assertFields(shown, ('source_id', 'revision', 'page', 'unit_id', 'box', 'label', 'caption', 'description'))
        self.assertEqual((shown['page'], shown['unit_id'], shown['box']), (2, 'page-2', self.FIGURE['box']))
        self.assertTrue(Path(self.op('source.render', figures=[figure['id']])['images'][0]['path']).is_file())

        self.op('source.readings.save', **self.pdf_ref, readings=[{'page': 3, 'text': 'Problems'}])
        status = next(s for s in self.op('course.status')['sources'] if s['id'] == self.pdf['id'])
        self.assertEqual((status['pages_read'], status['problem_pages'], status['verification']), (3, 1, 'verified'))

    def test_invalid_reading(self):
        for reading in ({'page': 4, 'text': 'Out of range'}, {'page': 1, 'text': 'x', 'figures': [{**self.FIGURE, 'description': ''}]},
                        {'page': 1, 'text': 'x', 'figures': [{**self.FIGURE, 'box': [0.1, 0.2, 1.4, 0.6]}]}):
            self.refused('invalid_reading', 'source.readings.save', **self.pdf_ref, readings=[reading])
        self.refused('invalid_reading', 'source.readings.save', **self.pdf_ref, readings=[{'page': 1, 'text': 'a'}, {'page': 1, 'text': 'b'}])


class ChatTeaching(Contract):
    """The deprecated chat-teaching operations keep working as docs/chat-teaching-operations.md documents them."""

    def test_a_side_question_in_chat(self):
        question = self.op('interaction.record', id='q1', role='user', text='Why the cross term?', concept_id='states')['interaction']
        self.assertFields(question, ('id', 'role', 'text', 'concept_id', 'sequence', 'source_refs', 'source_context_concept_id'))
        self.assertEqual(self.op('interaction.record', id='q1', role='user', text='Why the cross term?', concept_id='states')['interaction'], question,
                         'an identical retry succeeds')
        self.refused('id_conflict', 'interaction.record', id='q1', role='user', text='Another question')
        opened = self.op('sidequestion.open', id='s1', interaction_id='q1', category='local', depth='long', rationale='Needs the algebra',
                         strategy='worked_example')['branch']
        self.assertEqual(opened['id'], 's1')
        self.op('interaction.record', id='a1', role='assistant', text='Expand |a + b|^2.', concept_id='states')
        answered = self.op('sidequestion.answer', id='s1', answer_interaction_id='a1')['branch']
        self.assertEqual(answered['status'], 'waiting', 'a long answer waits for the learner')
        self.assertEqual(self.op('session.resume')['active_branch']['id'], 's1')
        self.op('sidequestion.continue', id='s1')
        self.assertIsNone(self.op('session.resume')['active_branch'])

        self.op('interaction.record', id='q2', role='user', text='What happens on measurement?', concept_id='states')
        self.op('interaction.record', id='a2', role='assistant', text='Roughly: squared components.', concept_id='states')
        promise = self.op('deferred.create', id='d1', interaction_id='q2', provisional_answer_interaction_id='a2', target_concept_id='outcomes')
        self.assertEqual(promise['deferred_explanation']['status'], 'pending')
        due = self.op('mainline.enter', request_id=str(uuid.uuid4()), concept_id='outcomes', goal='Measure', next_step='Start')['due_explanations']
        self.assertEqual([d['id'] for d in due], ['d1'])


class Commands(Contract):
    """docs/stability.md: the commands and the flags their --help lists keep their meaning; `courses` keeps its fields."""
    FLAGS = {None: {'--version', '--workspace', '--course', '--request'}, 'setup': {'--no-launcher', '--no-open', '--language'},
             'open': {'--port', '--no-browser'}, 'stop': set(), 'courses': set(), 'doctor': set(), 'export': {'--out', '--level'},
             'import': {'--name', '--fresh', '--keep-notes'}}

    def command(self, *args):
        env = self.environment()
        return subprocess.run([sys.executable, '-m', 'throughline', *args], text=True, encoding='utf-8', capture_output=True, cwd=ROOT, env=env, timeout=60)

    def test_every_command_keeps_its_flags(self):
        import re
        for command, flags in self.FLAGS.items():
            with self.subTest(command):
                shown = self.command(*([command] if command else []), '--help')
                self.assertEqual(shown.returncode, 0, shown.stderr)
                listed = set(re.findall(r'(--[a-z][a-z-]*)', shown.stdout)) - {'--help'}
                self.assertEqual(sorted(flags - listed), [], f'{command or "the operation entrypoint"} keeps its flags')
        level = self.command('export', '--help').stdout
        self.assertTrue(all(name in level for name in ('route', 'lessons', 'everything')))

    def test_courses_keeps_its_fields(self):
        listed = self.command('courses')
        self.assertEqual(listed.returncode, 0, listed.stderr)
        response = json.loads(listed.stdout)
        self.assertTrue(response['ok'])
        self.assertEqual(response['result']['root'], str(self.home / 'library'))
        [course] = response['result']['courses']
        self.assertFields(course, ('name', 'path', 'title', 'sources', 'concepts', 'needs_review', 'current', 'goal', 'updated', 'archived'))
        self.assertEqual({k: course[k] for k in ('name', 'title', 'sources', 'concepts', 'current', 'goal', 'archived')},
                         {'name': 'quantum', 'title': 'Introductory Quantum Mechanics', 'sources': 1, 'concepts': 3,
                          'current': 'States and global phase', 'goal': 'Understand interference and measurement', 'archived': False})

    def test_export_and_import_answer_in_an_envelope(self):
        package = self.home / 'quantum.throughline'
        exported = self.command('export', 'quantum', '--level', 'lessons', '--out', str(package))
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertFields(json.loads(exported.stdout)['result'], ('path', 'size', 'level', 'title', 'sources', 'contents'))
        imported = self.command('import', str(package), '--name', 'copy')
        self.assertEqual(imported.returncode, 0, imported.stderr)
        result = json.loads(imported.stdout)['result']
        self.assertFields(result, ('name', 'path', 'title', 'level', 'mode', 'sources'))
        self.assertEqual((result['name'], result['level'], result['mode']), ('copy', 'lessons', 'fresh'))
        refused = self.command('import', str(package), '--name', 'copy2', '--keep-notes')
        self.assertEqual((refused.returncode, json.loads(refused.stdout)['error']['code']), (1, 'invalid_request'), 'only Everything keeps notes')
        damaged = self.home / 'damaged.throughline'
        damaged.write_bytes(b'not a zip')
        refused = self.command('import', str(damaged))
        self.assertEqual((refused.returncode, json.loads(refused.stdout)['error']['code']), (1, 'invalid_package'))


if __name__ == '__main__':
    unittest.main()
