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

    def test_verify_records_reviewed_units_atomically_against_current_revision(self):
        model = self.model()
        model['coverage'] = model['coverage'][:1]
        self.call('curriculum.save', **model)
        line2 = {**self.refs[0], 'unit_id': 'line-2'}
        self.call('curriculum.verify', error='invalid_review', reviews=[{**self.refs[0], 'verification': 'verified', 'verification_note': 'Matches'},
                                                                        {**line2, 'verification': 'verified', 'verification_note': ' '}])
        self.assertEqual(self.call('curriculum.coverage')['units'][0]['verification'], 'pending')
        self.call('curriculum.verify', reviews=[{**self.refs[0], 'verification': 'verified', 'verification_note': 'Compared with the original line'},
                                                {**line2, 'verification': 'pending', 'verification_note': 'Formula sign unclear'}])
        units = {(u['source_id'], u['unit_id']): u for u in self.call('curriculum.coverage')['units']}
        self.assertEqual(units[(self.refs[0]['source_id'], 'line-1')]['verification'], 'verified')
        reviewed = units[(self.refs[0]['source_id'], 'line-2')]
        self.assertEqual((reviewed['disposition'], reviewed['concept_ids'], reviewed['verification'], reviewed['verification_note']),
                         ('mapped', ['projection'], 'pending', 'Formula sign unclear'))
        self.call('position.save', position={'concept_id': 'state', 'next_step': 'Read'})
        self.assertEqual(self.call('curriculum.context')['sources'][0]['verification'], 'verified')
        path = self.base / 'lecture.md'
        path.write_text('Revised', encoding='utf-8')
        self.call('source.register', path=str(path))
        self.call('curriculum.verify', error='invalid_review', reviews=[{**self.refs[0], 'verification': 'verified', 'verification_note': 'Matches'}])
