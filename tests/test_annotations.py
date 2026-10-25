import tempfile
import unittest

from guided_learning.api import execute
from guided_learning.store import OperationError, Store
from support import host_client


class Runner:
    prompts = []

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        emit({'kind': 'final', 'text': 'A lesson about states.'})
        emit({'kind': 'complete'})


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}, {'id': 'spin', 'title': 'Spin'}],
                   'route': ['state', 'spin'], 'coverage': []})


class Annotations(unittest.TestCase):
    def test_operations_validate_where_an_annotation_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            save = lambda **fields: execute(tmp, {'op': 'annotations.save', **fields})
            source = {'source_id': 's', 'revision': 'r', 'unit_id': 'p1', 'page': 3}
            highlight = save(id='h', kind='highlight', concept_id='state', passage='  a passage ', source=source)['annotation']
            self.assertEqual(highlight['passage'], 'a passage')
            self.assertEqual(highlight['source']['page'], 3)
            for fields, code in (
                ({'kind': 'highlight', 'concept_id': 'state', 'passage': 'x'}, 'invalid_request'),
                ({'kind': 'highlight', 'concept_id': 'state', 'passage': 'x', 'turn_id': 'missing'}, 'invalid_request'),
                ({'kind': 'note', 'concept_id': 'state'}, 'invalid_request'),
                ({'kind': 'bookmark', 'concept_id': 'state', 'passage': 'x'}, 'invalid_request'),
                ({'kind': 'bookmark', 'concept_id': 'nowhere'}, 'unknown_concept'),
                ({'kind': 'scribble', 'concept_id': 'state'}, 'invalid_request'),
            ):
                with self.assertRaises(OperationError) as raised:
                    save(id='bad', **fields)
                self.assertEqual(raised.exception.code, code, fields)
            save(id='n', kind='note', concept_id='spin', note='Ask about Stern-Gerlach')
            edited = save(id='h', kind='bookmark', concept_id='spin', note='Revisit')['annotation']
            self.assertEqual((edited['kind'], edited['concept_id'], edited['note']), ('highlight', 'state', 'Revisit'))
            with self.assertRaises(OperationError):
                save(id='n', note='')
            self.assertEqual([a['id'] for a in execute(tmp, {'op': 'annotations.list', 'concept_id': 'spin'})['annotations']], ['n'])
            execute(tmp, {'op': 'annotations.delete', 'id': 'n'})
            with self.assertRaises(OperationError) as raised:
                execute(tmp, {'op': 'annotations.delete', 'id': 'n'})
            self.assertEqual(raised.exception.code, 'unknown_annotation')

    def test_answers_and_exercises_take_their_own_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            store = Store(tmp)
            with store.db:
                store.put('streams', 'answer', {'id': 'answer', 'channel': 'sidequestion', 'concept_id': 'spin'})
                store.put('streams', 'prep', {'id': 'prep', 'channel': 'preparation', 'concept_id': 'spin'})
                store.put('practice_tasks', 'task', {'id': 'task', 'concept_id': 'spin', 'question': 'Q'})
            store.db.close()
            save = lambda **fields: execute(tmp, {'op': 'annotations.save', **fields})['annotation']
            answer = save(id='a', kind='highlight', concept_id='state', turn_id='answer', passage='in the answer')
            exercise = save(id='e', kind='highlight', task_id='task', passage='in the exercise', note='tricky')
            self.assertEqual((answer['concept_id'], exercise['concept_id'], exercise['task_id']), ('spin', 'spin', 'task'))
            for fields in ({'turn_id': 'prep'}, {'task_id': 'missing'}, {'task_id': 'task', 'turn_id': 'answer'}):
                with self.assertRaises(OperationError):
                    save(id='bad', kind='highlight', passage='x', **fields)

    def test_learner_annotations_round_trip_and_never_reach_the_teacher(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            runner = Runner()
            client, host = host_client(tmp, runner=runner)
            with client:
                client.post('/api/lessons', json={'id': 'one', 'prompt': 'Explain the state'})
                host.wait('one', 5)
                made = client.post('/api/annotations', json={'kind': 'highlight', 'concept_id': 'state', 'turn_id': 'one',
                                                             'passage': 'about states', 'note': 'PRIVATE-NOTE'})
                self.assertEqual(made.status_code, 200, made.text)
                identifier = made.json()['annotation']['id']
                client.post('/api/annotations', json={'kind': 'bookmark', 'concept_id': 'state'})
                self.assertEqual(client.put(f'/api/annotations/{identifier}', json={'note': 'PRIVATE-EDIT'}).json()['annotation']['note'], 'PRIVATE-EDIT')
                state = client.get('/api/state').json()
                self.assertEqual(sorted(a['kind'] for a in state['annotations']), ['bookmark', 'highlight'])
                client.post('/api/lessons', json={'id': 'two', 'prompt': 'Another pass'})
                host.wait('two', 5)
                self.assertNotIn('PRIVATE', runner.prompts[-1])
                self.assertEqual(client.delete(f'/api/annotations/{identifier}').status_code, 200)
                self.assertEqual(client.delete(f'/api/annotations/{identifier}').status_code, 404)
                self.assertEqual(client.post('/api/annotations', json={'kind': 'note', 'concept_id': 'state', 'note': 'x', 'extra': 1}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
