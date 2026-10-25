"""Which earlier exercises a chapter quiz asks again (ADR 0008)."""
import unittest

from guided_learning import practice
from test_review import MemoryStore

CHAPTER = {'id': 'one', 'concept_ids': ['a', 'b', 'c', 'd']}


class EarlierExercises(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        for cid in ('a', 'b', 'c'):
            self.store.put('streams', f'lesson-{cid}', {'id': f'lesson-{cid}', 'channel': 'mainline', 'status': 'completed', 'concept_id': cid})
        # A recap anchored to d is not a lesson of d, so d stays unstudied.
        self.store.put('streams', 'recap:1', {'id': 'recap:1', 'channel': 'mainline', 'status': 'completed', 'concept_id': 'd', 'chapter_id': 'one'})
        # c was skipped with the chapter and not studied since (its lesson predates the skip, say).
        self.store.put('evidence_deferred', 'chapter-skip:one:c', {'id': 'chapter-skip:one:c', 'concept_id': 'c'})

    def task(self, identifier, concept, kind=None, status=None, origin='self_created', **extra):
        history = [{'action': 'assess', 'kind': kind, 'outcome': 'needs_work' if kind == 'needs_work' else 'passed'}] if kind else []
        self.store.put('practice_tasks', identifier, {'id': identifier, 'concept_id': concept, 'question': identifier, 'origin': origin,
                                                      'status': status or ('attempted' if kind else 'pending'), 'history': history, **extra})

    def test_help_and_misses_first_then_set_aside_then_independent_spread_across_sections(self):
        self.task('a-independent', 'a', 'independent')
        self.task('a-hinted', 'a', 'hinted')
        self.task('a-missed', 'a', 'needs_work')
        self.task('b-later', 'b', status='deferred')
        self.task('b-independent', 'b', 'independent')
        self.task('b-open', 'b')  # never answered: still an open exercise, not quiz material
        self.task('b-review', 'b', 'hinted', origin='review')
        self.task('c-hinted', 'c', 'hinted')  # skipped section
        self.task('d-hinted', 'd', 'hinted')  # unstudied section
        self.task('quiz', 'd', 'hinted', origin='chapter_quiz', chapter_id='one', from_task_id='b-independent')
        self.assertEqual(practice.quiz_earlier(self.store, CHAPTER), ['a-hinted', 'a-missed', 'b-later'],
                         'one per section first, then the next best; at most three, listed in route order')

    def test_ones_asked_in_fewer_quizzes_come_first_among_equals(self):
        self.task('a-hinted', 'a', 'hinted')
        self.task('a-missed', 'a', 'needs_work')
        self.task('quiz', 'd', origin='chapter_quiz', chapter_id='one', from_task_id='a-hinted')
        self.assertEqual(practice.quiz_earlier(self.store, CHAPTER), ['a-missed', 'a-hinted'])

    def test_a_chapter_with_nothing_answered_asks_only_new_questions(self):
        self.task('a-open', 'a')
        self.assertEqual(practice.quiz_earlier(self.store, CHAPTER), [])


if __name__ == '__main__':
    unittest.main()
