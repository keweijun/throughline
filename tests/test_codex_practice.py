"""Operations Codex uses in Studio to change a section's exercises and to write review sets (issues #172, #173)."""
import tempfile
import unittest
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server import Host
from guided_learning.server.state import build
from guided_learning.store import OperationError


class CodexPractice(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = temp.name
        self.op('course.init', title='Data structures')
        problems = Path(self.path) / 'problems.md'
        problems.write_text('Problem 1\nProblem 2\nUnrelated', encoding='utf-8')
        source = self.op('source.register', path=str(problems))['source']
        self.ref = {'source_id': source['id'], 'revision': source['revision'], 'unit_id': 'line-1'}
        self.other = {**self.ref, 'unit_id': 'line-2'}
        exercises = [{'question': '1', **self.ref, 'required_concepts': ['stack']}, {'question': '2', **self.other, 'required_concepts': ['stack']}]
        self.op('curriculum.save', concepts=[{'id': 'stack', 'title': 'Stacks', 'links': [{**self.ref, 'detail': 'Problems'}], 'exercises': exercises},
                                              {'id': 'queue', 'title': 'Queues'}],
                route=['stack', 'queue'], coverage=[])

    def op(self, name, **fields):
        return execute(self.path, {'op': name, **fields})

    def refused(self, code, name, **fields):
        with self.assertRaises(OperationError) as caught:
            self.op(name, **fields)
        self.assertEqual(caught.exception.code, code, caught.exception)

    def test_codex_adds_exercises_as_worded_and_never_twice(self):
        added = self.op('practice.add', id='ps1', concept_id='stack', exercises=[
            {'question': 'Problem 1: is $\\{1,3,2\\}$ a stack permutation?', 'parts': ['(a) Decide', '(b) Explain'], 'origin': 'source', 'source_refs': [self.ref]},
            {'question': 'Trace a push and two pops.', 'origin': 'self_created'}])['tasks']
        self.assertEqual([t['id'] for t in added], ['ps1:0', 'ps1:1'])
        self.assertEqual(added[0]['exercise'], '1', 'the only exercise on its source unit')
        self.assertEqual((added[0]['status'], added[0]['history'], added[0]['parts']), ('pending', [], ['(a) Decide', '(b) Explain']))
        self.assertEqual(self.op('practice.add', id='ps1', concept_id='stack', exercises=[{'question': 'other'}])['tasks'], added, 'a replay')
        self.refused('exercise_exists', 'practice.add', id='again', concept_id='stack', exercises=[{'question': 'Problem 1 again', 'origin': 'source', 'source_refs': [self.ref], 'exercise': '1'}])
        self.refused('invalid_exercise', 'practice.add', id='bad', concept_id='stack', exercises=[{'question': 'From nowhere', 'origin': 'source', 'source_refs': [{**self.ref, 'unit_id': 'line-3'}]}])
        self.refused('invalid_exercise', 'practice.add', id='bad', concept_id='stack', exercises=[{'question': 'Which one?', 'origin': 'source', 'source_refs': [self.ref], 'exercise': '9'}])
        self.refused('invalid_request', 'practice.add', id='bad', concept_id='stack', exercises=[])
        self.refused('unknown_concept', 'practice.add', id='bad', concept_id='nowhere', exercises=[{'question': 'x', 'origin': 'self_created'}])
        self.assertEqual(len(self.op('practice.list')['tasks']), 2, 'a refused request adds nothing')

    def test_revising_keeps_the_learners_work_and_retiring_spares_it(self):
        task = self.op('practice.add', id='ps1', concept_id='stack', exercises=[
            {'question': 'Problem 1 with garbled formulas', 'parts': ['(a)', '(b)'], 'origin': 'source', 'source_refs': [self.ref]},
            {'question': 'Problem 2', 'origin': 'source', 'source_refs': [self.other]},
            {'question': 'A duplicate', 'origin': 'self_created'}])['tasks']
        host = Host(self.path, runner=Answer())
        try:
            answered = host.practice.act(task[0]['id'], 'assess', 'Part (a): yes')['turn']
            host.wait(answered['id'], 5)
        finally:
            host.close()
        revised = self.op('practice.revise', id=task[0]['id'], question='Problem 1 with $\\{1,3,2\\}$', parts=['(a) Decide', '(b) Explain'])['task']
        self.assertEqual(revised['question'], 'Problem 1 with $\\{1,3,2\\}$')
        self.assertEqual(revised['revisions'][0]['question'], 'Problem 1 with garbled formulas')
        self.assertEqual(revised['history'][-1]['parts'], ['correct', 'not_attempted'], 'the answer and its part statuses stay')
        self.assertEqual(self.op('practice.revise', id=task[0]['id'], question='Problem 1 with $\\{1,3,2\\}$')['task'], revised, 'no change, no revision')
        self.refused('exercise_answered', 'practice.revise', id=task[0]['id'], parts=['(a)', '(b)', '(c)'])
        self.refused('invalid_exercise', 'practice.revise', id=task[0]['id'], question=' ')
        self.refused('exercise_answered', 'practice.retire', id=task[0]['id'])

        retired = self.op('practice.retire', id=task[2]['id'], reason='Duplicate of Problem 2')['task']
        self.assertEqual((retired['status'], retired['retire_reason']), ('retired', 'Duplicate of Problem 2'))
        self.refused('unknown_exercise', 'practice.retire', id=task[2]['id'])
        self.refused('unknown_exercise', 'practice.revise', id=task[2]['id'], question='Back')
        host = Host(self.path)
        try:
            shown = build(host, ['practice'])['practice']['tasks']
        finally:
            host.close()
        self.assertEqual([t['id'] for t in shown], [task[0]['id'], task[1]['id']], 'a retired exercise is not shown')
        # A retired course exercise no longer blocks adding it again.
        self.op('practice.add', id='ps1-fixed', concept_id='stack', exercises=[{'question': 'A new one', 'origin': 'self_created'}])


class Answer:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': '{"feedback":"Part (a) is right.","parts":["correct","not_attempted"]}'})
        emit({'kind': 'complete'})


if __name__ == '__main__':
    unittest.main()
