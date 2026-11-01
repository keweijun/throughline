"""Course changes the teacher suggests making in Studio (ADR 0016)."""
import tempfile
import unittest

from guided_learning.api import execute
from guided_learning.store import OperationError
from support import host_client, settle

DECISION = ('<teaching-decision>{"depth":"short","category":"prerequisite","rationale":"needs Fourier series","suggest_supplement":false,'
            '"supplement_goal":""}</teaching-decision>')


class Runner:
    """Lessons suggest one change; side questions suggest another, with a teaching decision and a memory note."""

    def __init__(self):
        self.prompts = []

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if 'Branch decision protocol' in prompt:
            text = ('A wave packet is a sum of plane waves.\n' + DECISION
                    + '\n<course-change>{"request":"Add a section on Fourier series before States"}</course-change>'
                    + '\n<course-memory>{"entries":[{"kind":"taught_term","text":"wave packet"}]}</course-memory>')
        else:
            text = 'A state is a vector.\n<course-change>{"request":"Rebuild States with more worked examples"}</course-change>'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})
    execute(path, {'op': 'mainline.enter', 'concept_id': 'state', 'goal': 'states', 'next_step': 'read', 'request_id': 'p'})


class SuggestedChanges(unittest.TestCase):
    def test_a_reply_suggests_one_change_at_a_time_which_the_learner_opens_or_dismisses(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            runner = Runner()
            client, host = host_client(path, runner=runner)
            with client:
                host.start_turn({'id': 'one', 'concept_id': 'state', 'prompt': 'Teach'})
                settle(host)
                self.assertIn('<course-change>', runner.prompts[0])
                self.assertNotIn('Earlier suggestions', runner.prompts[0])
                changes = client.get('/api/state').json()['changes']
                self.assertEqual([(c['id'], c['request']) for c in changes], [('one', 'Rebuild States with more worked examples')])

                # A side question's suggestion supersedes the open one; its decision and memory note still count.
                host.questions.ask({'id': 'q', 'question': 'What is a wave packet?', 'main_turn_id': 'one'})
                settle(host)
                self.assertEqual(host.operation({'op': 'branch.read', 'id': 'q'})['branch']['decision']['category'], 'prerequisite')
                self.assertIn('wave packet', [e['text'] for e in host.operation({'op': 'memory.view'})['entries']])
                changes = client.get('/api/state').json()['changes']
                self.assertEqual([c['request'] for c in changes], ['Add a section on Fourier series before States'])

                response = client.put(f'/api/course-changes/{changes[0]["id"]}', json={'status': 'dismissed'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(client.get('/api/state').json()['changes'], [])
                self.assertEqual(client.put('/api/course-changes/branch:q', json={'status': 'later'}).status_code, 400)

                # The teacher sees what became of earlier suggestions, so it does not make them again.
                host.start_turn({'id': 'two', 'concept_id': 'state', 'prompt': 'Teach again'})
                settle(host)
                lesson = next(p for p in runner.prompts if p.endswith('Teach again') or 'request:\nTeach again' in p)
                self.assertIn('"status": "superseded"', lesson)
                self.assertIn('"status": "dismissed"', lesson)

    def test_a_suggestion_is_recorded_once_and_must_be_short(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            request = {'op': 'course_change.suggest', 'turn_id': 't', 'concept_id': 'state', 'request': 'Add a foundations chapter'}
            first = execute(path, request)['change']
            self.assertEqual(execute(path, {**request, 'request': 'Something else'})['change'], first)
            with self.assertRaises(OperationError):
                execute(path, {**request, 'turn_id': 'u', 'request': 'x' * 301})
            with self.assertRaises(OperationError):
                execute(path, {'op': 'course_change.resolve', 'id': 'missing', 'status': 'opened'})
            execute(path, {'op': 'course_change.resolve', 'id': 't', 'status': 'opened'})
            self.assertEqual(execute(path, {'op': 'course_change.list'})['changes'], [])


if __name__ == '__main__':
    unittest.main()
