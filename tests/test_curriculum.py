from support import call_cli
import tempfile
import unittest
from pathlib import Path


class CurriculumCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / 'course'
        self.call('course.init', title='Quantum')
        self.refs = []
        for name, text in [('lecture.md', 'States\nProjection'), ('problems.md', 'Projection exercise')]:
            path = self.base / name
            path.write_text(text, encoding='utf-8')
            source = self.call('source.register', path=str(path))['source']
            self.refs.append({'source_id': source['id'], 'revision': source['revision'], 'unit_id': 'line-1'})

    def call(self, op, error=None, workspace=None, **fields):
        return call_cli(self, workspace or self.workspace, op, error=error, **fields)

    def model(self):
        return {'concepts': [
            {'id': 'state', 'title': 'State', 'prerequisites': [], 'links': [{**self.refs[0], 'detail': 'Definition'}]},
            {'id': 'projection', 'title': 'Projection', 'prerequisites': ['state'], 'links': [{**self.refs[0], 'unit_id': 'line-2', 'detail': 'Formula'}, {**self.refs[1], 'detail': 'Application'}], 'notations': [{'symbol': 'c', 'meaning': 'Projection coefficient', **self.refs[1]}], 'exercises': [{'question': '7(a)', **self.refs[1]}]}
        ], 'route': ['state', 'projection'], 'coverage': [
            {**self.refs[0], 'disposition': 'mapped', 'concept_ids': ['state']},
            {**self.refs[0], 'unit_id': 'line-2', 'disposition': 'mapped', 'concept_ids': ['projection']},
            {**self.refs[1], 'disposition': 'mapped', 'concept_ids': ['projection']}
        ]}

    def test_cross_document_route_context_preserves_incremental_details_and_locators(self):
        self.call('curriculum.save', **self.model())
        self.call('position.save', position={'concept_id': 'projection', 'next_step': 'Compute coefficient'})
        context = self.call('curriculum.context')
        self.assertEqual(context['concept']['id'], 'projection')
        self.assertEqual(context['prerequisites'][0]['id'], 'state')
        self.assertEqual([item['text'] for item in context['sources']], ['Projection', 'Projection exercise'])
        self.assertEqual(context['concept']['notations'][0]['symbol'], 'c')
        self.assertEqual(context['concept']['exercises'][0]['question'], '7(a)')
        coverage = self.call('curriculum.coverage')
        self.assertEqual(len(coverage['units']), 3)
        self.assertTrue(all(unit['disposition'] == 'mapped' for unit in coverage['units']))
        self.assertTrue(all(unit['verification'] == 'pending' for unit in coverage['units']))
    def test_invalid_references_cycles_and_out_of_order_prerequisites_preserve_previous_route(self):
        self.call('curriculum.save', **self.model())
        bad = self.model()
        bad['concepts'][0]['links'][0]['unit_id'] = 'page-900'
        self.call('curriculum.save', error='invalid_reference', **bad)
        bad = self.model()
        bad['concepts'][0]['prerequisites'] = ['missing']
        self.call('curriculum.save', error='invalid_reference', **bad)
        bad = self.model()
        bad['concepts'][0]['prerequisites'] = ['projection']
        self.call('curriculum.save', error='prerequisite_cycle', **bad)
        bad = self.model()
        bad['route'].reverse()
        self.call('curriculum.save', error='invalid_route', confirm_reorder=True, **bad)
        self.assertEqual(self.call('curriculum.view')['route'], ['state', 'projection'])
    def test_deferred_units_need_reason_and_source_changes_reopen_coverage(self):
        model = self.model()
        model['coverage'][1] = {**model['coverage'][1], 'disposition': 'deferred', 'concept_ids': []}
        self.call('curriculum.save', error='invalid_coverage', **model)
        model['coverage'][1]['reason'] = 'Return after reviewing states'
        self.call('curriculum.save', **model)
        self.call('position.save', position={'concept_id': 'projection', 'progress': 'Explained'})
        path = self.base / 'lecture.md'
        path.write_text('Changed states\nProjection\nNew detail', encoding='utf-8')
        self.call('source.register', path=str(path))
        coverage = self.call('curriculum.coverage')
        changed = [u for u in coverage['units'] if u['source_id'] == self.refs[0]['source_id']]
        self.assertEqual([u['disposition'] for u in changed], ['needs_review', 'needs_review', 'unmapped'])
        self.assertEqual(len(coverage['stale_mappings']), 2)
        self.assertEqual(self.call('course.status')['position']['progress'], 'Explained')
        context = self.call('curriculum.context')
        self.assertTrue(context['sources'][0]['stale'])
        self.assertFalse(context['sources'][1]['stale'])
    def test_changing_relative_order_requires_confirmation_but_new_nodes_do_not(self):
        model = self.model()
        model['concepts'].append({'id': 'notation', 'title': 'Notation', 'prerequisites': [], 'links': []})
        model['route'].append('notation')
        self.call('curriculum.save', **model)
        model['route'] = ['notation', 'state', 'projection']
        self.call('curriculum.save', error='confirmation_required', **model)
        self.call('curriculum.save', confirm_reorder=True, **model)
        self.assertEqual(self.call('curriculum.view')['route'], ['notation', 'state', 'projection'])
        model['concepts'].append({'id': 'extra', 'title': 'Extra', 'prerequisites': []})
        model['route'].append('extra')
        self.call('curriculum.save', **model)
    def test_mapped_coverage_requires_actual_concept_link_and_current_revision(self):
        model = self.model()
        model['coverage'][0]['concept_ids'] = ['projection']
        self.call('curriculum.save', error='invalid_coverage', **model)
        path = self.base / 'lecture.md'
        path.write_text('Revised', encoding='utf-8')
        self.call('source.register', path=str(path))
        self.call('curriculum.save', error='invalid_coverage', **self.model())


class ChapterCLI(CurriculumCLI):
    def chapter(self, concepts, coverage=(), **fields):
        return self.call('curriculum.chapter.save', concepts=list(concepts), coverage=list(coverage), **fields)

    def test_chapters_are_built_one_at_a_time_and_keep_the_route_in_chapter_order(self):
        self.call('curriculum.outline', chapters=[{'id': 'states', 'title': 'States'}, {'id': 'measure', 'title': 'Measurement'}])
        self.assertEqual(self.call('curriculum.view')['route'], [])
        state, projection = self.model()['concepts']
        self.chapter([state], [self.model()['coverage'][0]], chapter_id='states', summary='What a state represents')
        model = self.call('curriculum.view')
        self.assertEqual(model['route'], ['state'])
        self.assertEqual(model['chapters'][1]['concept_ids'], [])
        self.call('position.save', position={'concept_id': 'state'})
        self.assertEqual(self.call('curriculum.context')['chapter']['id'], 'states')
        self.chapter([projection], self.model()['coverage'][1:], chapter_id='measure')
        model = self.call('curriculum.view')
        self.assertEqual(model['route'], ['state', 'projection'])
        self.assertEqual(len(model['coverage']), 3)
        self.assertEqual(model['chapters'][0]['summary'], 'What a state represents')
        view = self.call('curriculum.chapter.view', chapter_id='measure')
        self.assertEqual([c['id'] for c in view['concepts']], ['projection'])
        self.assertEqual(len(view['coverage']), 2)
        self.assertEqual(self.call('curriculum.context', concept_id='projection')['chapter']['index'], 1)

    def test_prerequisites_must_come_from_earlier_or_built_chapters(self):
        self.call('curriculum.outline', chapters=[{'id': 'states', 'title': 'States'}, {'id': 'measure', 'title': 'Measurement'}])
        state, projection = self.model()['concepts']
        self.chapter([projection], chapter_id='measure', error='invalid_reference')
        self.chapter([state], chapter_id='states')
        self.chapter([projection], chapter_id='measure')
        self.chapter([{**state, 'prerequisites': ['projection']}], chapter_id='states', error='prerequisite_cycle')
        self.chapter([], chapter_id='measure', error='invalid_route')
        self.chapter([state], chapter_id='missing', error='unknown_chapter')

    def test_moving_concepts_or_reordering_chapters_needs_confirmation(self):
        self.call('curriculum.outline', chapters=[{'id': 'states', 'title': 'States'}, {'id': 'measure', 'title': 'Measurement'}])
        state, projection = self.model()['concepts']
        projection['prerequisites'] = []
        self.chapter([state, projection], chapter_id='states')
        self.chapter([projection], chapter_id='measure')
        self.assertEqual(self.call('curriculum.view')['chapters'][0]['concept_ids'], ['state'])
        self.call('curriculum.outline', chapters=[{'id': 'measure', 'title': 'Measurement'}, {'id': 'states', 'title': 'States'}], error='confirmation_required')
        self.call('curriculum.outline', chapters=[{'id': 'states', 'title': 'States'}], error='invalid_chapters')
        self.call('curriculum.outline', chapters=[{'id': 'states', 'title': 'Quantum states'}, {'id': 'measure', 'title': 'Measurement'}, {'id': 'later', 'title': 'Later'}])
        self.assertEqual([c['title'] for c in self.call('curriculum.view')['chapters']], ['Quantum states', 'Measurement', 'Later'])

    def test_existing_flat_routes_are_grouped_by_outline_and_full_saves_keep_chapters(self):
        self.call('curriculum.save', **self.model())
        self.call('curriculum.outline', chapters=[{'id': 'one', 'title': 'One'}], error='invalid_chapters')
        self.call('curriculum.outline', chapters=[{'id': 'one', 'title': 'One', 'concept_ids': ['state']}, {'id': 'two', 'title': 'Two', 'concept_ids': ['projection']}])
        self.call('curriculum.save', **self.model())
        self.assertEqual(len(self.call('curriculum.view')['chapters']), 2)
        model = self.model()
        model['concepts'].append({'id': 'extra', 'title': 'Extra'})
        model['route'].append('extra')
        self.call('curriculum.save', error='invalid_chapters', **model)
        chapters = self.call('curriculum.view')['chapters']
        chapters[1]['concept_ids'].append('extra')
        self.call('curriculum.save', chapters=chapters, **model)

    def test_a_source_unit_shared_by_two_chapters_keeps_both_mappings(self):
        self.call('curriculum.outline', chapters=[{'id': 'states', 'title': 'States'}, {'id': 'measure', 'title': 'Measurement'}])
        state, projection = self.model()['concepts']
        shared = self.refs[1]
        state = {**state, 'links': state['links'] + [shared]}
        self.chapter([state], [{**shared, 'disposition': 'mapped', 'concept_ids': ['state']}], chapter_id='states')
        self.chapter([projection], [{**shared, 'disposition': 'mapped', 'concept_ids': ['projection']}], chapter_id='measure')
        entry = next(e for e in self.call('curriculum.view')['coverage'] if e['source_id'] == shared['source_id'])
        self.assertEqual(entry['concept_ids'], ['state', 'projection'])

    def test_sections_keep_their_core_question_objective_and_overview(self):
        model = self.model()
        framing = {'core_question': 'What is a state?', 'objective': 'Write a normalized state',
                   'overview': {'core_problem': 'States are vectors', 'steps': ['Kets', 'Normalization']}}
        model['concepts'][0].update(framing)
        self.call('curriculum.save', **model)
        self.assertEqual({k: self.call('curriculum.view')['concepts'][0][k] for k in framing}, framing)
        for bad in ({'core_question': 3}, {'overview': 'text'}, {'overview': {'steps': 'Kets'}}, {'overview': {'next': ['x']}}):
            model = self.model()
            model['concepts'][0].update(bad)
            self.call('curriculum.save', error='invalid_request', **model)
