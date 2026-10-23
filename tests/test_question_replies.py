"""Follow-ups retain one durable branch and a frozen, complete conversation."""
import tempfile
import unittest
from guided_learning.api import execute
from guided_learning.store import Store
from tests.support import host_client


class Replies(unittest.TestCase):
    def test_reply_http_history_idempotency_and_reopen(self):
        class Runner:
            def run(self, prompt, cwd, emit, cancel):
                emit({'kind': 'final', 'text': 'Use $E=mc^2$ to explain the first answer.'})
                emit({'kind': 'complete'})
        with tempfile.TemporaryDirectory() as root:
            execute(root, {'op': 'course.init', 'title': 'Replies'})
            execute(root, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'A'}], 'route': ['a'], 'coverage': []})
            execute(root, {'op': 'mainline.enter', 'concept_id': 'a', 'goal': 'A', 'next_step': 'Practice', 'request_id': 'p'})
            client, host = host_client(root, Runner())
            with client:
                client.post('/api/questions', json={'id': 'z', 'question': 'First question'})
                host.wait('branch:z', 3)
                client.post('/api/questions', json={'id': 'a', 'question': 'Second question'})
                host.wait('branch:a', 3)
                # Legacy records acquire their creation time from the original stream.
                store = Store(root)
                branch = store.get('web_branches', 'z'); branch.pop('created_at')
                store.put('web_branches', 'z', branch); store.db.commit(); store.db.close()
                questions = client.get('/api/state').json()['questions']
                self.assertEqual([q['id'] for q in questions], ['z', 'a'])
                before = execute(root, {'op': 'course.status'})['position']
                body = {'id': 'r1', 'question': 'Explain the formula', 'selection': '$E=mc^2$'}
                response = client.post('/api/questions/z/replies', json=body)
                self.assertEqual(response.status_code, 200, response.text)
                tid = response.json()['reply']['turn_id']; host.wait(tid, 3)
                turn = execute(root, {'op': 'stream.read', 'id': tid})['turn']
                conversation = turn['prompt_snapshot']['branch']['conversation']
                self.assertEqual(conversation[0]['question'], 'First question')
                self.assertIn('$E=mc^2$', conversation[0]['answer'])
                self.assertIn('Continue this same side-question conversation', host.build_prompt(turn))
                self.assertEqual(client.post('/api/questions/z/replies', json=body).status_code, 200)
                self.assertNotEqual(client.post('/api/questions/z/replies', json={**body, 'question': 'Different'}).status_code, 200)
                response = client.post('/api/questions/z/replies', json={'id': 'r2', 'question': 'Why squared?'})
                tid2 = response.json()['reply']['turn_id']; host.wait(tid2, 3)
                next_turn = execute(root, {'op': 'stream.read', 'id': tid2})['turn']
                self.assertEqual(len(next_turn['prompt_snapshot']['branch']['conversation']), 2)
                self.assertEqual(len(turn['prompt_snapshot']['branch']['conversation']), 1)
                self.assertEqual(execute(root, {'op': 'course.status'})['position'], before)
            branch = execute(root, {'op': 'branch.read', 'id': 'z'})['branch']
            self.assertEqual(len(branch['replies']), 2)
            self.assertEqual(len(execute(root, {'op': 'branch.list'})['branches']), 2)

    def test_reply_waits_for_complete_parent(self):
        with tempfile.TemporaryDirectory() as root:
            execute(root, {'op': 'course.init', 'title': 'Replies'})
            execute(root, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'A'}], 'route': ['a'], 'coverage': []})
            execute(root, {'op': 'mainline.enter', 'concept_id': 'a', 'goal': 'A', 'next_step': 'Practice', 'request_id': 'p'})
            execute(root, {'op': 'branch.begin', 'id': 'q', 'question': 'Why?'})
            with self.assertRaisesRegex(ValueError, 'earlier reply'):
                execute(root, {'op': 'branch.reply', 'id': 'q', 'reply_id': 'r', 'question': 'Again?'})
            self.assertEqual(execute(root, {'op': 'branch.read', 'id': 'q'})['branch']['replies'], [])
