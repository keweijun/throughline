"""The spaced review schedule (ADR 0008), computed from assessment evidence with an injected clock."""
import unittest
from datetime import datetime

from guided_learning import review
from guided_learning.store import OperationError

DAY = review.DAY
# Noon, so a few hours either way stays on the same local day.
T0 = datetime(2026, 3, 2, 12).timestamp()


class MemoryStore:
    """The two calls the schedule makes on a course store, over plain dictionaries."""

    def __init__(self):
        self.data = {}

    def get(self, namespace, key, default=None):
        return self.data.get(namespace, {}).get(key, default)

    def put(self, namespace, key, value):
        self.data.setdefault(namespace, {})[key] = value
        return value

    def list(self, namespace):
        return [v for _, v in sorted(self.data.get(namespace, {}).items())]


class Schedule(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.put('curriculum', 'model', {'route': ['a', 'b', 'c', 'd', 'e', 'f', 'g'], 'concepts': []})
        self.sequence = 0

    def assess(self, concept, at, kind='independent', origin='practice', tests=None, task=None):
        """Record one assessment the way practice.complete does: a task, an assessment interaction and the evidence."""
        self.sequence += 1
        task = task or f'task-{self.sequence}'
        if not self.store.get('practice_tasks', task):
            self.store.put('practice_tasks', task, {'id': task, 'concept_id': concept, 'origin': origin, 'history': [],
                                                    **({'tests_concept_ids': tests} if tests else {})})
        self.store.put('interactions', f'i{self.sequence}', {'id': f'i{self.sequence}', 'sequence': self.sequence})
        item = {'id': f'e{self.sequence:03}', 'concept_id': concept, 'exercise_id': task, 'assessment_id': f'i{self.sequence}',
                'kind': kind, 'outcome': 'needs_work' if kind == 'needs_work' else 'passed'}
        if at is not None:
            item['assessed_at'] = at
        self.store.put('evidence', item['id'], item)
        history = self.store.get('practice_tasks', task)['history']
        history.append({'action': 'assess', 'outcome': item['outcome']})
        return task

    def schedule(self, now):
        return review.schedule(self.store, {'now': now})

    def section(self, now, concept):
        return next(s for s in self.schedule(now)['sections'] if s['concept_id'] == concept)

    def test_nothing_is_reviewable_before_a_pass(self):
        self.assess('a', T0, kind='needs_work')
        result = self.schedule(T0 + 10 * DAY)
        self.assertEqual((result['reviewable'], result['due'], result['upcoming']), (0, [], 0))

    def test_any_pass_makes_a_section_due_a_day_later(self):
        self.assess('a', T0, kind='hinted')
        self.assertEqual(self.schedule(T0 + DAY - 60)['due'], [])
        self.assertEqual(self.schedule(T0 + DAY - 60)['upcoming'], 1)
        due = self.schedule(T0 + DAY)['due']
        self.assertEqual([s['concept_id'] for s in due], ['a'])
        self.assertEqual(due[0]['interval_days'], 1)

    def test_unaided_review_passes_climb_the_intervals_and_stay_at_sixty_days(self):
        at = T0
        self.assess('a', at)
        for expected in (3, 7, 21, 60, 60):
            at += 400 * DAY
            self.assess('a', at, origin='review')
            self.assertEqual(self.section(at, 'a')['interval_days'], expected)
            self.assertEqual(self.section(at, 'a')['due_at'], at + expected * DAY)

    def test_an_assisted_review_pass_repeats_the_interval_and_needs_work_starts_over(self):
        self.assess('a', T0)
        self.assess('a', T0 + DAY, origin='review')
        self.assess('a', T0 + 4 * DAY, origin='review')
        self.assertEqual(self.section(T0 + 4 * DAY, 'a')['interval_days'], 7)
        self.assess('a', T0 + 11 * DAY, kind='hinted', origin='review')
        self.assertEqual(self.section(T0 + 11 * DAY, 'a')['interval_days'], 7)
        self.assess('a', T0 + 18 * DAY, kind='needs_work', origin='review')
        state = self.section(T0 + 18 * DAY, 'a')
        self.assertEqual((state['interval_days'], state['due_at']), (1, T0 + 19 * DAY))

    def test_ordinary_practice_restarts_the_wait_without_moving_the_step(self):
        self.assess('a', T0)
        self.assess('a', T0 + DAY, origin='review')
        self.assess('a', T0 + 2 * DAY)
        state = self.section(T0 + 2 * DAY, 'a')
        self.assertEqual((state['interval_days'], state['due_at']), (3, T0 + 5 * DAY))
        self.assess('a', T0 + 3 * DAY, kind='needs_work')
        self.assertEqual(self.section(T0 + 3 * DAY, 'a')['interval_days'], 3, 'a failed ordinary exercise is not a review')

    def test_a_chapter_quiz_question_reviews_every_section_it_tests(self):
        self.assess('a', T0)
        self.assess('b', T0)
        self.assess('c', T0 + 2 * DAY, origin='chapter_quiz', tests=['a', 'b'])
        now = T0 + 2 * DAY
        self.assertEqual(self.section(now, 'a')['interval_days'], 3)
        self.assertEqual(self.section(now, 'b')['interval_days'], 3)
        self.assertNotIn('c', [s['concept_id'] for s in self.schedule(now)['sections']], 'the question was filed under c but tested a and b')
        self.assertEqual(self.schedule(now)['done_today'], 2)

    def test_due_sections_come_oldest_first_and_at_most_five_a_day(self):
        for offset, concept in enumerate('gfedcba'):
            self.assess(concept, T0 + offset * 60)
        now = T0 + 30 * DAY
        result = self.schedule(now)
        self.assertEqual([s['concept_id'] for s in result['due']], list('gfedc'))
        self.assertEqual(result['waiting'], 2)
        self.assess('g', now - 60, origin='review')
        self.assess('f', now - 30, origin='review')
        result = self.schedule(now)
        self.assertEqual(result['done_today'], 2)
        self.assertEqual([s['concept_id'] for s in result['due']], list('edc'), 'reviews done today count toward the cap')
        self.assertEqual(result['waiting'], 2)
        result = self.schedule(now + DAY)
        self.assertEqual([s['concept_id'] for s in result['due']], list('edcba'), 'tomorrow the cap starts again')

    def test_a_started_review_stays_listed_until_answered(self):
        self.assess('a', T0)
        self.store.put('practice_tasks', 'r1', {'id': 'r1', 'concept_id': 'a', 'origin': 'review', 'status': 'pending', 'history': []})
        due = self.schedule(T0 + DAY)['due']
        self.assertEqual(due[0]['task_id'], 'r1')
        self.assess('a', T0 + DAY + 60, origin='review', task='r1')
        self.assertEqual(self.schedule(T0 + DAY + 120)['due'], [])

    def test_not_now_postpones_a_due_section_by_one_day(self):
        self.assess('a', T0)
        with self.assertRaises(OperationError) as raised:
            review.postpone(self.store, {'concept_id': 'a', 'now': T0 + 60})
        self.assertEqual(raised.exception.code, 'not_due')
        now = T0 + 2 * DAY
        review.postpone(self.store, {'concept_id': 'a', 'now': now})
        self.assertEqual(self.schedule(now)['due'], [])
        self.assertEqual(self.schedule(now + DAY)['due'][0]['concept_id'], 'a')
        self.assess('a', now + DAY, origin='review')
        self.assertEqual(self.section(now + DAY, 'a')['due_at'], now + 4 * DAY, 'a later review replaces the postponement')
        with self.assertRaises(OperationError) as raised:
            review.postpone(self.store, {'concept_id': 'z', 'now': now})
        self.assertEqual(raised.exception.code, 'not_reviewable')

    def test_sections_skipped_with_their_chapter_are_not_scheduled(self):
        self.assess('a', T0)
        self.store.put('evidence_deferred', 'chapter-skip:one:a', {'id': 'chapter-skip:one:a', 'concept_id': 'a'})
        self.assertEqual(self.schedule(T0 + 5 * DAY)['reviewable'], 0)
        self.store.put('evidence_resolutions', 'r', {'id': 'r', 'deferred_id': 'chapter-skip:one:a'})
        self.assertEqual(len(self.schedule(T0 + 5 * DAY)['due']), 1)

    def test_an_undated_assessment_reads_as_long_ago(self):
        self.assess('a', None)
        self.assertEqual([s['concept_id'] for s in self.schedule(T0)['due']], ['a'])

    def test_sections_no_longer_on_the_route_are_not_scheduled(self):
        self.assess('gone', T0)
        self.assertEqual(self.schedule(T0 + 5 * DAY)['reviewable'], 0)


if __name__ == '__main__':
    unittest.main()
