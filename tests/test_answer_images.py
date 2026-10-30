import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from guided_learning import images as attached
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
                uploaded = client.post('/api/images', content=PNG, headers={'Content-Type': 'image/png'})
                self.assertEqual(uploaded.status_code, 200, uploaded.text)
                name = uploaded.json()['image']
                stored = Path(path) / 'answer_images' / name
                self.assertEqual(stored.read_bytes(), PNG)
                self.assertEqual(client.get('/api/images/' + name).content, PNG)

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
                self.assertEqual(client.post('/api/images', content=b'not a picture', headers={'Content-Type': 'image/png'}).status_code, 415)
                self.assertEqual(client.post('/api/images', content=b'<svg/>', headers={'Content-Type': 'image/svg+xml'}).status_code, 415)
                huge = client.post('/api/images', content=b'', headers={'Content-Type': 'image/png', 'Content-Length': str(64 * 1024 * 1024)})
                self.assertEqual(huge.status_code, 413)
                self.assertEqual(client.get('/api/images/..%2Fcourse.sqlite3').status_code, 404)
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
                name = attached.save(path, PNG[:64])
                runner.reply = '{"feedback":"Check the constant.","outcome":"needs_work"}'
                host.wait(host.practice.act(tid, 'assess', 'See my working', images=[name])['turn']['id'], 5)
            interactions = execute(path, {'op': 'session.resume'})['recent_interactions']
            answer = next(i for i in interactions if i['id'].startswith('practice-answer:'))
            self.assertEqual((answer['text'], answer['images']), ('See my working', [name]))


class AttachedImages(unittest.TestCase):
    """Side questions, their follow-ups, questions about an exercise and learner notes take images too."""

    def test_side_question_and_follow_up_images_reach_the_teacher(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'mainline.enter', 'concept_id': 'a', 'goal': 'A', 'next_step': 'Practice', 'request_id': 'p'})
            runner = Runner()
            runner.reply = 'Look at the sign.'
            first, second = attached.save(path, PNG[:64]), attached.save(path, PNG[:65])
            client, host = host_client(path, runner=runner)
            with client:
                asked = client.post('/api/questions', json={'id': 'q', 'question': 'Why this sign?', 'images': [first]})
                self.assertEqual(asked.status_code, 200, asked.text)
                host.wait('branch:q', 5)
                self.assertEqual(runner.images, [str(attached.path(path, first))])
                self.assertIn('1 image to this question', runner.prompt)
                reply = client.post('/api/questions/q/replies', json={'id': 'r', 'question': 'And here?', 'images': [second, first]})
                self.assertEqual(reply.status_code, 200, reply.text)
                host.wait(reply.json()['reply']['turn_id'], 5)
                self.assertEqual(runner.images, [str(attached.path(path, n)) for n in (second, first)])
                self.assertIn('2 images to this follow-up', runner.prompt)
                again = client.post('/api/questions/q/replies', json={'id': 'r', 'question': 'And here?', 'images': [first]})
                self.assertEqual(again.status_code, 409, 'the same reply id with other images is a different reply')
                plain = client.post('/api/questions/q/replies', json={'id': 'r2', 'question': 'No picture'})
                host.wait(plain.json()['reply']['turn_id'], 5)
                self.assertEqual(runner.images, [], 'a follow-up without images sends none, even in a thread that had some')
                questions = client.get('/api/state').json()['questions']
                self.assertEqual(questions[0]['images'], [first])
                self.assertEqual(questions[0]['replies'][0]['images'], [second, first])
                self.assertNotIn('images', questions[0]['replies'][1])
                unknown = client.post('/api/questions', json={'id': 'u', 'question': 'Hm', 'images': ['0' * 64 + '.png']})
                self.assertEqual(unknown.status_code, 404)

    def test_question_about_an_exercise_sends_its_images(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            runner = Runner()
            client, host = host_client(path, runner=runner)
            with client:
                host.wait(client.post('/api/practice/generate', json={'concept_id': 'a'}).json()['turn']['id'], 5)
                tid = host.practice.state()['tasks'][0]['id']
                name = attached.save(path, PNG[:64])
                runner.reply = '{"feedback":"It means the area."}'
                asked = client.post(f'/api/practice/tasks/{tid}/ask', json={'question': 'What is this figure?', 'images': [name]})
                self.assertEqual(asked.status_code, 200, asked.text)
                host.wait(asked.json()['turn']['id'], 5)
                self.assertEqual(runner.images, [str(attached.path(path, name))])
                self.assertIn('1 image to the question', runner.prompt)
                entry = client.get('/api/state').json()['practice']['tasks'][0]['history'][-1]
                self.assertEqual((entry['action'], entry['images']), ('ask', [name]))
                hinted = client.post(f'/api/practice/tasks/{tid}/hint', json={'images': [name]})
                host.wait(hinted.json()['turn']['id'], 5)
                self.assertEqual(runner.images, [], 'a hint takes no images')

    def test_learner_notes_keep_images(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            name, other = attached.save(path, PNG[:64]), attached.save(path, PNG[:65])
            client, _ = host_client(path, runner=Runner())
            with client:
                only = client.post('/api/annotations', json={'kind': 'note', 'concept_id': 'a', 'images': [name]})
                self.assertEqual(only.status_code, 200, only.text)
                note = only.json()['annotation']
                self.assertEqual((note['note'], note['images']), ('', [name]))
                edited = client.put(f"/api/annotations/{note['id']}", json={'note': 'My sketch'}).json()['annotation']
                self.assertEqual(edited['images'], [name], 'editing the text keeps the images')
                edited = client.put(f"/api/annotations/{note['id']}", json={'note': 'My sketch', 'images': [other, name]}).json()['annotation']
                self.assertEqual(edited['images'], [other, name])
                cleared = client.put(f"/api/annotations/{note['id']}", json={'note': 'My sketch', 'images': []}).json()['annotation']
                self.assertNotIn('images', cleared)
                self.assertEqual(client.put(f"/api/annotations/{note['id']}", json={'note': '', 'images': []}).status_code, 409)
                bookmark = client.post('/api/annotations', json={'kind': 'bookmark', 'concept_id': 'a', 'images': [name]})
                self.assertEqual(bookmark.status_code, 409)


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
