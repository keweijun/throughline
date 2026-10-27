import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from guided_learning.api import execute
from support import host_client

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * (3 * 1024 * 1024)
QUESTION = '{"questions":[{"question":"Integrate x by hand.","origin":"self_created","source_refs":[]}]}'


class Runner:
    """A fake teacher that takes images; the ones without an `images` parameter keep working for text-only turns."""
    def __init__(self):
        self.reply, self.images, self.prompt = QUESTION, None, ''

    def run(self, prompt, cwd, emit, cancel, images=()):
        self.prompt, self.images = prompt, list(images)
        emit({'kind': 'final', 'text': self.reply}); emit({'kind': 'complete'})


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Calculus'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'Integrals'}], 'route': ['a'], 'coverage': []})


class AnswerImages(unittest.TestCase):
    def test_uploaded_images_are_stored_with_the_answer_and_sent_to_the_teacher(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            runner = Runner()
            client, host = host_client(path, runner=runner)
            with client:
                host.wait(client.post('/api/practice/generate', json={'concept_id': 'a'}).json()['turn']['id'], 5)
                self.assertEqual(runner.images, [], 'a turn without images passes none')
                tid = host.practice.state()['tasks'][0]['id']
                # A phone photo is larger than the JSON body limit, so images have their own upload route.
                uploaded = client.post('/api/practice/images', content=PNG, headers={'Content-Type': 'image/png'})
                self.assertEqual(uploaded.status_code, 200, uploaded.text)
                name = uploaded.json()['image']
                stored = Path(path) / 'answer_images' / name
                self.assertEqual(stored.read_bytes(), PNG)
                self.assertEqual(client.get('/api/practice/images/' + name).content, PNG)

                runner.reply = '{"feedback":"Correct.","outcome":"passed"}'
                answered = client.post(f'/api/practice/tasks/{tid}/assess', json={'answer': '', 'images': [name]})
                self.assertEqual(answered.status_code, 200, answered.text)
                host.wait(answered.json()['turn']['id'], 5)
                self.assertEqual(runner.images, [str(stored.resolve())])
                self.assertIn('1 image', runner.prompt)
                task = client.get('/api/state').json()['practice']['tasks'][0]
                self.assertEqual(task['history'][-1]['images'], [name])
                job = next(j for j in host.practice.state()['jobs'] if j['action'] == 'assess')
                self.assertEqual(job['images'], [name])

    def test_upload_and_answer_reject_what_is_not_an_attached_image(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            runner = Runner()
            client, host = host_client(path, runner=runner)
            with client:
                host.wait(client.post('/api/practice/generate', json={'concept_id': 'a'}).json()['turn']['id'], 5)
                tid = host.practice.state()['tasks'][0]['id']
                self.assertEqual(client.post('/api/practice/images', content=b'not a picture', headers={'Content-Type': 'image/png'}).status_code, 415)
                self.assertEqual(client.post('/api/practice/images', content=b'<svg/>', headers={'Content-Type': 'image/svg+xml'}).status_code, 415)
                huge = client.post('/api/practice/images', content=b'', headers={'Content-Type': 'image/png', 'Content-Length': str(64 * 1024 * 1024)})
                self.assertEqual(huge.status_code, 413)
                self.assertEqual(client.get('/api/practice/images/..%2Fcourse.sqlite3').status_code, 404)
                missing = client.post(f'/api/practice/tasks/{tid}/assess', json={'answer': 'x', 'images': ['0' * 64 + '.png']})
                self.assertEqual(missing.status_code, 404, missing.text)
                empty = client.post(f'/api/practice/tasks/{tid}/assess', json={'answer': ' ', 'images': []})
                self.assertEqual(empty.status_code, 409)

    def test_answer_interaction_references_its_images(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            runner = Runner()
            client, host = host_client(path, runner=runner)
            with client:
                host.wait(client.post('/api/practice/generate', json={'concept_id': 'a'}).json()['turn']['id'], 5)
                tid = host.practice.state()['tasks'][0]['id']
                name = host.practice.save_image(PNG[:64])
                runner.reply = '{"feedback":"Check the constant.","outcome":"needs_work"}'
                host.wait(host.practice.act(tid, 'assess', 'See my working', [name])['turn']['id'], 5)
            interactions = execute(path, {'op': 'session.resume'})['recent_interactions']
            answer = next(i for i in interactions if i['id'].startswith('practice-answer:'))
            self.assertEqual((answer['text'], answer['images']), ('See my working', [name]))


class RunnerInput(unittest.TestCase):
    def test_codex_runner_sends_images_as_local_image_inputs(self):
        from guided_learning.codex import CodexRunner
        with tempfile.TemporaryDirectory() as tmp:
            script, seen = Path(tmp) / 'server.py', Path(tmp) / 'turn.json'
            script.write_text('''import sys,json
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); i=r.get('id')
 if m=='initialize': print(json.dumps({'id':i,'result':{}}),flush=True)
 if m=='thread/start': print(json.dumps({'id':i,'result':{'thread':{'id':'t'}}}),flush=True)
 if m=='turn/start':
  open(%r,'w').write(json.dumps(r['params'])); sys.exit(0)
''' % str(seen), encoding='utf-8')
            with self.assertRaises(RuntimeError):
                CodexRunner(command=[sys.executable, str(script)]).run('assess', tmp, lambda e: None, threading.Event(), images=['/w/a.png', '/w/b.jpg'])
            self.assertEqual(json.loads(seen.read_text())['input'], [{'type': 'text', 'text': 'assess'},
                                                                     {'type': 'localImage', 'path': '/w/a.png'},
                                                                     {'type': 'localImage', 'path': '/w/b.jpg'}])


if __name__ == '__main__':
    unittest.main()
