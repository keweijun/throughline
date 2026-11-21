"""What Studio writes into Review (issue #229, ADR 0026): sessions and mock exams (`drill.write`), sheets (`sheet.save`),
exercises (`practice.add`), each linked to the hand-off that asked for it through `handoff_id`."""
import tempfile
import unittest
from pathlib import Path

from guided_learning.api import execute
from guided_learning.store import OperationError

APPLY = {'kind': 'apply', 'question': 'Push 1, 2, 3 and pop twice: what is left?', 'parts': ['(a) the stack', '(b) why'], 'tests_concept_ids': ['stack'], 'marks': 6}
RECALL = {'kind': 'recall', 'question': 'Which end does pop use?', 'idea': 'LIFO', 'correct': 0, 'tests_concept_ids': ['stack'],
          'options': [{'text': 'The top', 'explanation': 'Last in, first out.'}, {'text': 'The bottom', 'explanation': 'That is a queue.'}]}


class StudioWrites(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.op('course.init', title='Data structures')
        self.op('curriculum.outline', chapters=[{'id': 'linear', 'title': 'Linear structures'}, {'id': 'trees', 'title': 'Trees'}])
        self.op('curriculum.chapter.save', chapter_id='linear', concepts=[{'id': 'stack', 'title': 'Stacks'}, {'id': 'queue', 'title': 'Queues'}])
        self.op('curriculum.chapter.save', chapter_id='trees', concepts=[{'id': 'bst', 'title': 'Binary search trees'}])

    def tearDown(self):
        self.tmp.cleanup()

    def op(self, name, **request):
        return execute(self.root, {'op': name, **request})

    def refused(self, code, name, **request):
        with self.assertRaises(OperationError) as caught:
            self.op(name, **request)
        self.assertEqual(caught.exception.code, code)

    def study(self, cid):
        self.op('stream.start', id='lesson-' + cid, concept_id=cid, prompt='Teach', channel='mainline')
        self.op('stream.event', id='lesson-' + cid, attempt=1, sequence=1, kind='final', text='Taught.')
        self.op('stream.event', id='lesson-' + cid, attempt=1, sequence=2, kind='complete')

    def sent(self, identifier):
        self.op('handoff.save', id=identifier, place={'kind': 'review', 'way': 'mock'}, label='Mock exam', request='Write me a mock exam', thread_id='thread-1')

    def test_a_mock_exam_is_a_session_answered_in_review_and_linked_to_its_hand_off(self):
        self.refused('nothing_to_review', 'drill.write', id='mock', title='Mock exam', questions=[APPLY])
        self.study('stack')
        self.sent('review:1')
        written = self.op('drill.write', id='mock', title='Mock exam: linear structures', exam=True, note='Two questions, 30 minutes.',
                          scope={'chapter_ids': ['linear']}, questions=[APPLY, RECALL], handoff_id='review:1')
        self.assertEqual(written['task_ids'], ['mock:written:00', 'mock:written:01'])
        session = next(s for s in self.op('drill.list')['sessions'] if s['id'] == 'mock')
        self.assertEqual((session['origin'], session['title'], session['exam'], session['note'], session['sections']),
                         ('studio', 'Mock exam: linear structures', True, 'Two questions, 30 minutes.', ['stack']))
        tasks = {t['id']: t for t in self.op('practice.list')['tasks']}
        self.assertEqual((tasks['mock:written:00']['marks'], tasks['mock:written:00']['session_id'], tasks['mock:written:00']['origin']), (6, 'mock', 'review'))
        self.assertEqual(tasks['mock:written:01']['options'][tasks['mock:written:01']['correct']]['text'], 'The top')
        handoff = self.op('handoff.list')['handoffs'][0]
        self.assertEqual(handoff['result']['kind'], 'session')
        self.assertEqual((handoff['result']['id'], handoff['result']['title']), ('mock', 'Mock exam: linear structures'))
        self.assertEqual(self.op('drill.write', id='mock', title='Again', questions=[])['task_ids'], written['task_ids'], 'a replay')

    def test_a_session_is_refused_whole_when_a_question_is_wrong(self):
        self.study('stack')
        self.refused('invalid_review_question', 'drill.write', id='m', title='T', questions=[{**APPLY, 'tests_concept_ids': ['queue']}])
        self.refused('invalid_review_question', 'drill.write', id='m', title='T', questions=[{**RECALL, 'correct': 7}])
        self.refused('invalid_review_question', 'drill.write', id='m', title='T', questions=[{**APPLY, 'marks': 0}])
        self.refused('invalid_review_question', 'drill.write', id='m', title='T', questions=[APPLY] * 31)
        self.refused('invalid_request', 'drill.write', id='m', questions=[APPLY])
        self.assertEqual(self.op('drill.list')['sessions'], [], 'nothing is saved')
        self.assertEqual(len(self.op('drill.write', id='m', title='Thirty', questions=[APPLY] * 30)['task_ids']), 30)

    def test_a_sheet_is_saved_replaced_and_removed_and_links_its_hand_off(self):
        self.refused('unknown_concept', 'sheet.save', id='f', title='Formulas', markdown='x', scope={'chapter_ids': ['graphs']})
        self.refused('invalid_request', 'sheet.save', id='f', title='Formulas', markdown='  ')
        self.sent('review:2')
        first = self.op('sheet.save', id='f', title='Formula sheet', markdown='# Stacks\n$O(1)$ push', scope={'chapter_ids': ['linear']}, handoff_id='review:2')['sheet']
        again = self.op('sheet.save', id='f', title='Formula sheet, shorter', markdown='# Stacks', scope={'concept_ids': ['stack']})['sheet']
        self.assertEqual((again['created_at'], again['scope']), (first['created_at'], {'concept_ids': ['stack']}))
        self.assertEqual([s['title'] for s in self.op('sheet.list')['sheets']], ['Formula sheet, shorter'])
        self.assertEqual(self.op('handoff.list')['handoffs'][0]['result']['kind'], 'sheet')
        self.op('sheet.delete', id='f')
        self.assertEqual(self.op('sheet.list')['sheets'], [])
        self.refused('unknown_sheet', 'sheet.delete', id='f')

    def test_exercises_added_for_a_hand_off_link_to_their_section(self):
        self.sent('chapter:3')
        self.op('practice.add', id='ps1', concept_id='stack', exercises=[{'question': 'Reverse a word with a stack.', 'origin': 'self_created'}], handoff_id='chapter:3')
        result = self.op('handoff.list')['handoffs'][0]['result']
        self.assertEqual((result['kind'], result['concept_id'], result['task_ids']), ('exercises', 'stack', ['ps1:0']))

    def test_a_result_saved_before_its_hand_off_is_recorded_waits_for_it(self):
        self.study('stack')
        self.op('sheet.save', id='f', title='Formula sheet', markdown='x', handoff_id='review:9')
        self.assertEqual(self.op('handoff.list')['handoffs'], [], 'not shown until the app records the hand-off')
        self.sent('review:9')
        handoff = self.op('handoff.list')['handoffs'][0]
        self.assertEqual((handoff['thread_id'], handoff['result']['id']), ('thread-1', 'f'))
        self.refused('invalid_request', 'sheet.save', id='g', title='T', markdown='x', handoff_id='')


if __name__ == '__main__':
    unittest.main()
