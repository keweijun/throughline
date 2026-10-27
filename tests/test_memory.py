import tempfile
import unittest

from guided_learning.api import execute
from guided_learning.store import OperationError


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}, {'id': 'spin', 'title': 'Spin'}],
                   'route': ['state', 'spin'], 'coverage': []})
    for i, role in ((1, 'user'), (2, 'assistant'), (3, 'user')):
        execute(path, {'op': 'interaction.record', 'id': f'i{i}', 'role': role, 'text': f'turn {i}', 'concept_id': 'state'})


class CourseMemory(unittest.TestCase):
    def test_note_records_entries_and_preferences_wait_for_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            note = {'entries': [{'kind': 'taught_term', 'text': 'plane wave'},
                                {'kind': 'difficulty', 'text': 'Charge bookkeeping in Hamiltonians', 'interaction_ids': ['i1', 'missing']},
                                {'kind': 'preference', 'text': 'One step at a time'},
                                {'kind': 'analogy', 'text': 'like a guitar string'}]}
            result = execute(tmp, {'op': 'memory.note', 'turn_id': 't1', 'concept_id': 'state', 'interaction_ids': ['i2', 'i3'], 'note': note})
            self.assertEqual(len(result['recorded']), 3)
            entries = {e['kind']: e for e in execute(tmp, {'op': 'memory.view'})['entries']}
            self.assertEqual(entries['taught_term']['status'], 'active')
            self.assertEqual(entries['difficulty']['interaction_ids'], ['i1', 'i2', 'i3'])
            self.assertEqual(entries['preference']['status'], 'suggested')
            self.assertEqual(entries['taught_term']['concept_id'], 'state')
            # Only what is in effect reaches a prompt.
            self.assertEqual(execute(tmp, {'op': 'memory.prompt'})['memory'],
                             {'taught_terms': [{'term': 'plane wave', 'concept_id': 'state'}],
                              'difficulties': [{'id': entries['difficulty']['id'], 'idea': 'Charge bookkeeping in Hamiltonians'}]})
            execute(tmp, {'op': 'memory.confirm', 'id': entries['preference']['id']})
            self.assertEqual(execute(tmp, {'op': 'memory.prompt'})['memory']['preferences'], ['One step at a time'])
            # The same turn's note is recorded once, however often the host replays it.
            again = execute(tmp, {'op': 'memory.note', 'turn_id': 't1', 'concept_id': 'state', 'interaction_ids': ['i2'], 'note': note})
            self.assertEqual(again['recorded'], [])
            self.assertEqual(len(execute(tmp, {'op': 'memory.view'})['entries']), 3)

    def test_duplicates_merge_and_cleared_difficulties_leave_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            execute(tmp, {'op': 'memory.note', 'turn_id': 't1', 'concept_id': 'state', 'interaction_ids': ['i1'],
                          'note': {'entries': [{'kind': 'difficulty', 'text': 'Independence of joint probabilities'}]}})
            execute(tmp, {'op': 'memory.note', 'turn_id': 't2', 'concept_id': 'spin', 'interaction_ids': ['i3'],
                          'note': {'entries': [{'kind': 'difficulty', 'text': ' independence of joint  probabilities'}]}})
            [entry] = execute(tmp, {'op': 'memory.view'})['entries']
            self.assertEqual(entry['interaction_ids'], ['i1', 'i3'])
            execute(tmp, {'op': 'memory.note', 'turn_id': 't3', 'concept_id': 'spin', 'interaction_ids': ['i2'], 'note': {'cleared': [entry['id'], 'nope']}})
            self.assertEqual(execute(tmp, {'op': 'memory.view'})['entries'][0]['status'], 'cleared')
            self.assertEqual(execute(tmp, {'op': 'memory.prompt'})['memory'], {})

    def test_learner_edits_and_deletes_and_a_tombstone_blocks_the_same_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            execute(tmp, {'op': 'memory.note', 'turn_id': 't1', 'concept_id': 'state', 'interaction_ids': ['i1'],
                          'note': {'entries': [{'kind': 'preference', 'text': 'Give the tedious integrals'}, {'kind': 'taught_term', 'text': 'ket'}]}})
            preference, term = sorted(execute(tmp, {'op': 'memory.view'})['entries'], key=lambda e: e['kind'])
            edited = execute(tmp, {'op': 'memory.save', 'id': term['id'], 'text': 'ket $|\\psi\\rangle$'})['entry']
            self.assertEqual(edited['text'], 'ket $|\\psi\\rangle$')
            with self.assertRaises(OperationError) as error:
                execute(tmp, {'op': 'memory.save', 'id': term['id'], 'text': '  '})
            self.assertEqual(error.exception.code, 'invalid_request')
            with self.assertRaises(OperationError) as error:
                execute(tmp, {'op': 'memory.confirm', 'id': term['id']})
            self.assertEqual(error.exception.code, 'invalid_request')
            execute(tmp, {'op': 'memory.delete', 'id': preference['id']})
            self.assertEqual([e['id'] for e in execute(tmp, {'op': 'memory.view'})['entries']], [term['id']])
            # The teacher cites the same interaction again, in other words: still deleted.
            result = execute(tmp, {'op': 'memory.note', 'turn_id': 't2', 'concept_id': 'state', 'interaction_ids': ['i3'],
                                   'note': {'entries': [{'kind': 'preference', 'text': 'Show every integral', 'interaction_ids': ['i1']}]}})
            self.assertEqual(result['recorded'], [])
            self.assertEqual(len(result['skipped']), 1)
            # New evidence for a different preference is still suggested.
            result = execute(tmp, {'op': 'memory.note', 'turn_id': 't3', 'concept_id': 'state', 'interaction_ids': ['i3'],
                                   'note': {'entries': [{'kind': 'preference', 'text': 'No hints when I am right'}]}})
            self.assertEqual(len(result['recorded']), 1)
            for op, code in (('memory.delete', 'unknown_memory_entry'), ('memory.confirm', 'unknown_memory_entry')):
                with self.assertRaises(OperationError) as error:
                    execute(tmp, {'op': op, 'id': preference['id']})
                self.assertEqual(error.exception.code, code)

    def test_invalid_notes_are_refused_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            for note in ('text', {'entries': 'x'}, {'entries': [{'kind': 'taught_term', 'text': 'x' * 400}]}):
                with self.assertRaises(OperationError):
                    execute(tmp, {'op': 'memory.note', 'turn_id': 't', 'concept_id': 'state', 'interaction_ids': [], 'note': note})
            self.assertEqual(execute(tmp, {'op': 'memory.view'})['entries'], [])


def seeded(path):
    """Duplicates, a cleared difficulty, both preference states and a tombstone."""
    course(path)
    def note(turn, ids, entries, cleared=()):
        return execute(path, {'op': 'memory.note', 'turn_id': turn, 'concept_id': 'state', 'interaction_ids': ids,
                              'note': {'entries': entries, 'cleared': list(cleared)}})['recorded']
    [term] = note('t1', ['i1'], [{'kind': 'taught_term', 'text': 'plane wave'}])
    [plural] = note('t2', ['i2'], [{'kind': 'taught_term', 'text': 'plane waves'}])
    [difficulty] = note('t3', ['i1'], [{'kind': 'difficulty', 'text': 'Charge bookkeeping'}])
    note('t4', ['i3'], [], cleared=[difficulty['id']])
    [suggested, confirmed, other, gone] = note('t5', ['i2'], [{'kind': 'preference', 'text': 'One step at a time'},
                                                              {'kind': 'preference', 'text': 'No hints when I am right'},
                                                              {'kind': 'preference', 'text': 'Step by step'},
                                                              {'kind': 'taught_term', 'text': 'ket'}])
    for entry in (confirmed, other):
        execute(path, {'op': 'memory.confirm', 'id': entry['id']})
    execute(path, {'op': 'memory.delete', 'id': gone['id']})
    return {'term': term['id'], 'plural': plural['id'], 'difficulty': difficulty['id'], 'suggested': suggested['id'],
            'confirmed': confirmed['id'], 'other': other['id'], 'deleted': gone['id']}


class Consolidation(unittest.TestCase):
    def consolidate(self, path, reply, error=None):
        request = {'op': 'memory.consolidate', 'turn_id': 'c', 'concept_id': 'state', 'reply': reply}
        if not error:
            return execute(path, request)
        before = execute(path, {'op': 'memory.view'})['entries']
        with self.assertRaises(OperationError) as caught:
            execute(path, request)
        self.assertEqual(caught.exception.code, error, reply)
        self.assertEqual(execute(path, {'op': 'memory.view'})['entries'], before)

    def test_merges_duplicates_and_prunes_cleared_entries_citing_what_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = seeded(tmp)
            result = self.consolidate(tmp, {'merge': [{'into': ids['term'], 'entries': [ids['plural']]}],
                                            'prune': [{'id': ids['difficulty'], 'reason': 'Cleared in practice'},
                                                      {'id': ids['suggested'], 'reason': 'Never confirmed'}]})
            self.assertEqual(result['changed'], [ids['term'], ids['plural'], ids['difficulty'], ids['suggested']])
            entries = {e['id']: e for e in execute(tmp, {'op': 'memory.view'})['entries']}
            self.assertEqual(set(entries), {ids['term'], ids['confirmed'], ids['other']})
            self.assertEqual(entries[ids['term']]['interaction_ids'], ['i1', 'i2'])
            self.assertEqual(entries[ids['term']]['text'], 'plane wave')
            record = execute(tmp, {'op': 'memory.consolidations'})['consolidations'][0]
            self.assertEqual((record['turn_id'], record['concept_id']), ('c', 'state'))
            self.assertEqual(record['merge'], [{'into': ids['term'], 'entries': [ids['plural']]}])
            self.assertEqual([p['id'] for p in record['prune']], [ids['difficulty'], ids['suggested']])
            # A merged or pruned entry is gone for the learner and cannot be edited back.
            with self.assertRaises(OperationError):
                execute(tmp, {'op': 'memory.save', 'id': ids['plural'], 'text': 'back'})
            # Replaying the same turn changes nothing.
            self.assertTrue(self.consolidate(tmp, {'merge': [], 'prune': [{'id': ids['term'], 'reason': 'x'}]})['replayed'])
            self.assertIn(ids['term'], {e['id'] for e in execute(tmp, {'op': 'memory.view'})['entries']})

    def test_confirmed_preferences_merge_only_with_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = seeded(tmp)
            self.consolidate(tmp, {'merge': [{'into': ids['suggested'], 'entries': [ids['other']]}]}, 'invalid_consolidation')
            self.consolidate(tmp, {'merge': [{'into': ids['confirmed'], 'entries': [ids['other']]}]})
            [preference] = [e for e in execute(tmp, {'op': 'memory.view'})['entries'] if e['status'] == 'confirmed']
            self.assertEqual(preference['text'], 'No hints when I am right')

    def test_refuses_whole_anything_but_merging_and_pruning_live_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = seeded(tmp)
            prune = lambda key: {'prune': [{'id': ids['difficulty'], 'reason': 'Cleared'}, {'id': key, 'reason': 'stale'}]}
            for reply in ('text', {'entries': [{'kind': 'preference', 'text': 'Be brief'}]},
                          {'merge': [{'into': ids['term'], 'entries': [ids['deleted']]}]},
                          {'merge': [{'into': ids['deleted'], 'entries': [ids['term']]}]},
                          {'merge': [{'into': ids['term'], 'entries': [ids['difficulty']]}]},
                          {'merge': [{'into': ids['term'], 'entries': []}]},
                          {'merge': [{'into': ids['term'], 'entries': [ids['term']]}]},
                          {'merge': [{'into': ids['term'], 'entries': [ids['plural']], 'text': 'Plane waves'}]},
                          prune(ids['deleted']), prune(ids['confirmed']), prune('missing'), prune(ids['difficulty']),
                          {'prune': [{'id': ids['plural']}]},
                          {'merge': [{'into': ids['term'], 'entries': [ids['plural']]}], 'prune': [{'id': ids['plural'], 'reason': 'x'}]}):
                self.consolidate(tmp, reply, 'invalid_consolidation')
            self.assertEqual(execute(tmp, {'op': 'memory.consolidations'})['consolidations'], [])


if __name__ == '__main__':
    unittest.main()
