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


if __name__ == '__main__':
    unittest.main()
