"""Review on request (ADR 0014): the review context, recall answers and warm-ups, read from the course with an injected clock."""
import unittest

from guided_learning import review
from guided_learning.store import OperationError

DAY = review.DAY
T0 = 1_800_000_000


class MemoryStore:
    """The calls the review module makes on a course store, over plain dictionaries."""

    def __init__(self):
        self.data = {}

    def get(self, namespace, key, default=None):
        return self.data.get(namespace, {}).get(key, default)

    def put(self, namespace, key, value):
        self.data.setdefault(namespace, {})[key] = value
        return value

    def list(self, namespace):
        return [v for _, v in sorted(self.data.get(namespace, {}).items())]

    shared = get

    def digest(self, namespace, project):
        return [project(v) for v in self.list(namespace)]


class ReviewContext(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.put('curriculum', 'model', {'route': ['a', 'b', 'c', 'd'], 'concepts': [
            {'id': 'a', 'title': 'A', 'objective': 'Use A'}, {'id': 'b', 'title': 'B'},
            {'id': 'c', 'title': 'C', 'prerequisites': ['a', 'b']}, {'id': 'd', 'title': 'D', 'prerequisites': ['c']}]})

    def lesson(self, cid, at):
        self.store.put('streams', 'lesson-' + cid, {'id': 'lesson-' + cid, 'channel': 'mainline', 'status': 'completed', 'concept_id': cid, 'started_at': at})

    def task(self, identifier, cid, **fields):
        return self.store.put('practice_tasks', identifier, {'id': identifier, 'concept_id': cid, 'question': identifier, 'origin': 'self_created',
                                                             'status': 'pending', 'history': [], **fields})

    def context(self, now, **request):
        return {s['id']: s for s in review.context(self.store, {'now': now, **request})['sections']}

    def test_studied_sections_with_days_since_practised_misses_and_set_aside_exercises(self):
        self.lesson('a', T0)
        self.lesson('b', T0 + DAY)
        self.task('missed', 'a', status='attempted', history=[{'action': 'assess', 'outcome': 'needs_work', 'parts': ['correct', 'not_yet']}])
        self.task('partly', 'a', status='attempted', history=[{'action': 'assess', 'outcome': 'needs_work', 'parts': ['correct', 'not_attempted']}])
        self.task('solved', 'a', status='attempted', history=[{'action': 'assess', 'outcome': 'passed', 'parts': ['correct']}])
        self.task('later', 'b', status='deferred')
        self.store.put('evidence', 'e1', {'id': 'e1', 'concept_id': 'a', 'assessment_id': 'i1', 'assessed_at': T0 + 2 * DAY})
        sections = self.context(T0 + 10 * DAY)
        self.assertEqual(list(sections), ['a', 'b'], 'studied sections in route order')
        self.assertEqual((sections['a']['days_since_practised'], sections['b']['days_since_practised']), (8, 9))
        self.assertEqual(sections['a']['recent_misses'], ['missed', 'partly'])
        self.assertEqual(sections['a']['objective'], 'Use A')
        self.assertEqual(sections['b']['set_aside'], ['later'])

    def test_sections_skipped_with_their_chapter_are_not_reviewed(self):
        self.lesson('a', T0)
        self.lesson('b', T0)
        self.store.put('evidence_deferred', 'chapter-skip:one:b', {'id': 'chapter-skip:one:b', 'concept_id': 'b'})
        self.assertEqual(list(self.context(T0)), ['a'])

    def test_earlier_review_questions_carry_their_outcomes(self):
        self.lesson('a', T0)
        self.task('r1', 'a', origin='review', set_id='s', kind='recall', options=[{'text': 'x'}, {'text': 'y'}], correct=0,
                  answer={'choice': 1, 'correct': False, 'at': T0 + DAY})
        self.task('r2', 'a', origin='review', set_id='s', kind='apply')
        earlier = review.context(self.store, {'now': T0})['earlier']
        self.assertEqual([(e['question'], e['outcome']) for e in earlier], [('r1', 'missed'), ('r2', 'unanswered')])
        self.assertIn('r1', self.context(T0)['a']['recent_misses'], 'a wrong recall answer is a miss')
        self.assertEqual(self.context(T0 + 3 * DAY)['a']['days_since_practised'], 2, 'a recall answer is practice')

    def test_only_an_option_of_a_recall_question_can_be_chosen(self):
        self.lesson('a', T0)
        self.task('r', 'a', origin='review', set_id='s', kind='recall', options=[{'text': 'x', 'explanation': ''}, {'text': 'y', 'explanation': ''}], correct=1)
        with self.assertRaises(OperationError):
            review.answer(self.store, {'task_id': 'r', 'choice': 2})
        self.task('plain', 'a')
        with self.assertRaises(OperationError):
            review.answer(self.store, {'task_id': 'plain', 'choice': 0})

    def test_warm_ups_offer_stale_studied_prerequisites_of_sections_not_started(self):
        self.lesson('a', T0)
        self.lesson('b', T0 + 5 * DAY)
        self.assertEqual(review.warm_ups(self.store, {'now': T0 + 6 * DAY})['warm_ups'], {})
        self.assertEqual(review.warm_ups(self.store, {'now': T0 + 8 * DAY})['warm_ups'], {'c': ['a']}, 'd builds on c, which is not studied')
        self.assertEqual(review.warm_ups(self.store, {'now': T0 + 13 * DAY})['warm_ups'], {'c': ['a', 'b']})
        self.lesson('c', T0 + 13 * DAY)
        self.assertNotIn('c', review.warm_ups(self.store, {'now': T0 + 13 * DAY})['warm_ups'], 'c has started')

    def test_a_dismissed_warm_up_is_not_offered_again(self):
        self.lesson('a', T0)
        review.dismiss_warm_up(self.store, {'concept_id': 'c'})
        self.assertEqual(review.warm_ups(self.store, {'now': T0 + 30 * DAY})['warm_ups'], {})


if __name__ == '__main__':
    unittest.main()
