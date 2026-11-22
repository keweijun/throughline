"""The mistakes book (issue #219): worked out from exercises, review answers and check answers, never stored."""
import unittest

from guided_learning import mistakes
from test_review import MemoryStore

T0 = 1_800_000_000


class Book(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()

    def assessed(self, identifier, at):
        self.store.put('evidence', identifier, {'id': identifier, 'concept_id': 'a', 'assessed_at': at})
        return identifier

    def task(self, identifier, history, **fields):
        return self.store.put('practice_tasks', identifier, {'id': identifier, 'concept_id': 'a', 'question': 'Find P.', 'origin': 'self_created',
                                                             'status': 'attempted', 'history': history, **fields})

    def assess(self, parts, at, answer='P = 1/2', feedback='Add amplitudes first.'):
        return {'action': 'assess', 'parts': parts, 'answer': answer, 'feedback': feedback,
                'outcome': 'passed' if all(p == 'correct' for p in parts) else 'needs_work', 'evidence_id': self.assessed(f'e{at}', at)}

    def check(self, lesson, turn, idea, correct, at, concept='a'):
        value = self.store.get('lessons', lesson) or {'id': lesson, 'concept_id': concept, 'steps': []}
        options = [{'text': 'Right', 'explanation': 'Because.'}, {'text': 'Wrong', 'explanation': 'Adds probabilities.'}]
        value['steps'].append({'title': 't', 'turn_id': turn, 'check': {'idea': idea, 'question': 'Which?', 'options': options, 'correct': 0},
                               'answer': {'choice': 0 if correct else 1, 'correct': correct, 'unsure': False, 'answered_at': at}})
        self.store.put('lessons', lesson, value)

    def book(self):
        return mistakes.entries(self.store)['entries']

    def test_each_missed_part_with_its_latest_miss_and_when_it_was_later_right(self):
        self.task('t1', [self.assess(['correct', 'not_yet'], T0), self.assess(['correct', 'partly_correct'], T0 + 10, answer='Closer'),
                         self.assess(['correct', 'correct'], T0 + 20)], parts=['(a) amplitude', '(b) probability'])
        self.task('t2', [self.assess(['not_yet'], T0 + 5)])
        self.task('t3', [self.assess(['correct'], T0 + 6)])
        entries = self.book()
        self.assertEqual([e['id'] for e in entries], ['part:t2:0', 'part:t1:1'], 'open first, then since got right')
        part = entries[1]
        self.assertEqual((part['part'], part['answer'], part['missed_at'], part['last_missed_at'], part['right_at']),
                         ('(b) probability', 'Closer', T0, T0 + 10, T0 + 20))
        self.assertNotIn('part', entries[0], 'a single-part exercise names no part')

    def test_a_miss_carried_forward_to_a_later_answer_is_not_missed_again(self):
        first = {**self.assess(['correct', 'not_yet'], T0), 'attempt': ['correct', 'not_yet']}
        # The second answer only redid part (a); `parts` still says (b) is not yet.
        second = {**self.assess(['correct', 'not_yet'], T0 + 10, answer='Redid (a)'), 'attempt': ['correct', 'not_attempted']}
        self.task('t1', [first, second], parts=['(a) amplitude', {'text': '(b) probability', 'concept_ids': ['b']}])
        entry = self.book()[0]
        self.assertEqual((entry['last_missed_at'], entry['answer']), (T0, 'P = 1/2'))
        self.assertEqual(entry['concept_ids'], ['b'], 'a part naming its sections is filed under them')

    def test_an_assessment_recorded_without_parts_is_read_from_its_outcome(self):
        self.task('old', [{'action': 'assess', 'outcome': 'needs_work', 'answer': 'x', 'feedback': 'y', 'evidence_id': self.assessed('e1', T0)}])
        self.assertEqual([e['id'] for e in self.book()], ['part:old:0'])

    def test_review_and_quiz_misses_name_the_sections_they_test_and_replaced_exercises_are_left_out(self):
        self.task('r1', [self.assess(['not_yet'], T0)], origin='review', tests_concept_ids=['a', 'b'])
        self.task('q1', [self.assess(['not_yet'], T0 + 1)], origin='chapter_quiz', chapter_id='c1')
        self.task('old', [self.assess(['not_yet'], T0 + 2)], status='replaced')
        found = {e['id']: e for e in self.book()}
        self.assertEqual(set(found), {'part:r1:0', 'part:q1:0'})
        self.assertEqual((found['part:r1:0']['kind'], found['part:r1:0']['concept_ids']), ('review', ['a', 'b']))
        self.assertEqual((found['part:q1:0']['kind'], found['part:q1:0']['chapter_id']), ('quiz', 'c1'))

    def test_a_wrong_recall_answer_is_marked_right_by_a_later_right_answer_on_its_idea(self):
        options = [{'text': '1', 'explanation': 'Add, then square.'}, {'text': '1/2', 'explanation': 'This adds probabilities.'}]
        self.task('recall', [], origin='review', idea='Amplitudes add', options=options, correct=0, answer={'choice': 1, 'correct': False, 'at': T0})
        entry = self.book()[0]
        self.assertEqual((entry['chosen'], entry['correct_answer'], entry['why'], entry['right_at']), ('1/2', '1', 'This adds probabilities.', None))
        self.check('l1', 's1', 'amplitudes add', True, T0 + 50)
        self.assertEqual(self.book()[0]['right_at'], T0 + 50, 'a later check on the same idea counts, matched as course memory matches it')

    def test_check_misses_become_a_mistake_only_when_they_repeat_on_one_idea(self):
        self.check('l1', 's1', 'Amplitudes add before squaring', False, T0)
        self.assertEqual(self.book(), [], 'one miss is a slip')
        self.check('l1', 's2', 'Amplitudes add before squaring', False, T0 + 10)
        entry = self.book()[0]
        self.assertEqual((entry['kind'], entry['turn_id'], entry['missed_at'], entry['last_missed_at']), ('check', 's2', T0, T0 + 10))
        self.check('l1', 's3', 'Amplitudes add before squaring', True, T0 + 20)
        self.assertEqual(self.book()[0]['right_at'], T0 + 20)
        self.check('l1', 's4', 'Amplitudes add before squaring', False, T0 + 30)
        self.assertIsNone(self.book()[0]['right_at'], 'missed again since')


if __name__ == '__main__':
    unittest.main()
