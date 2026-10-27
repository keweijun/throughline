import json
import tempfile
import unittest

from guided_learning.api import execute
from guided_learning.server import Host
from support import host_client

LESSON = ('A plane wave is $e^{ikx}$.\n<course-memory>{"entries":[{"kind":"taught_term","text":"plane wave"},'
          '{"kind":"preference","text":"One step at a time"}],"cleared":[]}</course-memory>')
ANSWER = ('Amplitudes add before squaring.\n<teaching-decision>{"depth":"short","category":"local","rationale":"local","suggest_supplement":false,'
          '"supplement_goal":""}</teaching-decision>\n<course-memory>{"entries":[{"kind":"taught_term","text":"amplitude"}]}</course-memory>')


class Runner:
    def __init__(self):
        self.prompts = []
        self.assessment = {}

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if 'Branch decision protocol' in prompt:
            text = ANSWER
        elif 'Practice only: return JSON {"questions"' in prompt:
            text = '{"questions":[{"question":"Normalize $e^{ikx}$ on a box.","origin":"self_created","source_refs":[]}]}'
        elif 'Assess the reasoning' in prompt:
            text = json.dumps(self.assessment)
        else:
            text = LESSON
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})
    execute(path, {'op': 'mainline.enter', 'concept_id': 'state', 'goal': 'states', 'next_step': 'read', 'request_id': 'p'})


def settle(app):
    for turn in app.brief_turns():
        app.wait(turn['id'], 5)


class MemoryFlow(unittest.TestCase):
    def test_teaching_turns_write_memory_and_later_prompts_carry_what_is_in_effect(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'annotations.save', 'id': 'n', 'kind': 'note', 'concept_id': 'state', 'note': 'PRIVATE-NOTE'})
            runner = Runner()
            app = Host(path, runner=runner)
            try:
                app.start_turn({'id': 'one', 'concept_id': 'state', 'prompt': 'Teach'})
                settle(app)
                self.assertIn('<course-memory>', runner.prompts[0])
                for rule in ('Use a taught term without defining it again', 'Derive or justify an example',
                             'Mention source verification or extraction quality only when'):
                    self.assertIn(rule, runner.prompts[0])
                self.assertNotIn('State uncertainty about formulas', runner.prompts[0])
                entries = {e['kind']: e for e in app.operation({'op': 'memory.view'})['entries']}
                self.assertEqual(entries['taught_term']['interaction_ids'], ['stream-user:one', 'stream:one'])
                self.assertEqual(entries['preference']['status'], 'suggested')

                app.questions.ask({'id': 'q', 'question': 'Why add amplitudes?', 'main_turn_id': 'one'})
                settle(app)
                self.assertEqual(app.operation({'op': 'branch.read', 'id': 'q'})['branch']['decision']['category'], 'local')
                snapshot = app.operation({'op': 'stream.read', 'id': 'branch:q'})['turn']['prompt_snapshot']
                self.assertEqual(snapshot['course_memory'], {'taught_terms': [{'term': 'plane wave', 'concept_id': 'state'}]})
                self.assertIn('amplitude', [e['text'] for e in app.operation({'op': 'memory.view'})['entries']])

                task = app.practice.state()['tasks'][0]
                runner.assessment = {'feedback': 'The norm is wrong again.', 'outcome': 'needs_work',
                                     'memory': {'entries': [{'kind': 'difficulty', 'text': 'Normalizing over a finite box'}]}}
                app.practice.act(task['id'], 'assess', 'N = 1')
                settle(app)
                difficulty = next(e for e in app.operation({'op': 'memory.view'})['entries'] if e['kind'] == 'difficulty')
                self.assertTrue(all(i.startswith(('practice-answer:', 'practice-feedback:')) for i in difficulty['interaction_ids']))

                app.operation({'op': 'memory.confirm', 'id': entries['preference']['id']})
                runner.assessment = {'feedback': 'Correct.', 'outcome': 'passed', 'memory': {'entries': [], 'cleared': [difficulty['id']]}}
                app.practice.act(task['id'], 'assess', 'N = 1/sqrt(L)')
                settle(app)
                self.assertEqual(next(e for e in app.operation({'op': 'memory.view'})['entries'] if e['kind'] == 'difficulty')['status'], 'cleared')

                app.start_turn({'id': 'two', 'concept_id': 'state', 'prompt': 'Again'})
                settle(app)
                snapshot = app.operation({'op': 'stream.read', 'id': 'two'})['turn']['prompt_snapshot']
                self.assertEqual(snapshot['course_memory']['preferences'], ['One step at a time'])
                self.assertNotIn('difficulties', snapshot['course_memory'])
                self.assertTrue(all('PRIVATE-NOTE' not in p for p in runner.prompts))
            finally:
                app.close()

    def test_memory_routes_view_edit_confirm_and_delete(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'memory.note', 'turn_id': 't', 'concept_id': 'state', 'interaction_ids': [],
                           'note': {'entries': [{'kind': 'preference', 'text': 'Give the tedious integrals'}, {'kind': 'taught_term', 'text': 'ket'}]}})
            client, host = host_client(path, runner=Runner())
            with client:
                memory = client.get('/api/state').json()['memory']
                preference = next(e for e in memory if e['kind'] == 'preference')
                term = next(e for e in memory if e['kind'] == 'taught_term')
                self.assertEqual(client.put(f'/api/memory/{term["id"]}', json={'text': 'bra-ket'}).json()['entry']['text'], 'bra-ket')
                self.assertEqual(client.post(f'/api/memory/{preference["id"]}/confirm').json()['entry']['status'], 'confirmed')
                self.assertEqual(client.post(f'/api/memory/{term["id"]}/confirm').status_code, 409)
                self.assertEqual(client.delete(f'/api/memory/{term["id"]}').status_code, 200)
                self.assertEqual(client.delete(f'/api/memory/{term["id"]}').status_code, 404)
                self.assertEqual(client.put(f'/api/memory/{preference["id"]}', json={'text': 'x', 'kind': 'difficulty'}).status_code, 400)
                self.assertEqual([e['text'] for e in client.get('/api/state').json()['memory']], ['Give the tedious integrals'])


if __name__ == '__main__':
    unittest.main()
