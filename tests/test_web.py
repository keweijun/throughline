import json
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from guided_learning.api import execute

class WebLearning(unittest.TestCase):
    def test_existing_course_stream_record_and_browser_origin_boundary(self):
        from guided_learning.web import create_server
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                self.prompt=prompt
                emit({'kind':'delta','text':'Lesson'})
                emit({'kind':'final','text':'Authoritative lesson.'})
                emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Quantum'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'state','title':'States'}],'route':['state'],'coverage':[]})
            runner=Runner()
            server=create_server(tmp,port=0,runner=runner)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            base='http://127.0.0.1:'+str(server.server_port)
            def post(path,data,origin=None):
                headers={'Content-Type':'application/json'}
                if origin: headers['Origin']=origin
                return urlopen(Request(base+path,json.dumps(data).encode(),headers),timeout=5)
            with post('/api/turns',{'id':'one','concept_id':'state','prompt':'Explain the state'}) as r:
                self.assertEqual(r.status,200)
            server.app.wait('one',5)
            state=json.load(urlopen(base+'/api/state'))
            self.assertEqual(state['turns'][0]['status'],'completed')
            self.assertEqual(state['session']['recent_interactions'][-1]['text'],'Authoritative lesson.')
            self.assertIn('States',runner.prompt)
            self.assertIn('sources',runner.prompt)
            self.assertIn('Teach in English by default',runner.prompt)
            self.assertIn('Use another language when the learner explicitly requests it',runner.prompt)
            with urlopen(base) as response:
                self.assertIn('<html lang="en">',response.read().decode('utf-8'))
            with self.assertRaises(HTTPError) as ctx:
                post('/api/turns',{'id':'evil','concept_id':'state','prompt':'x'},'https://evil.example')
            self.assertEqual(ctx.exception.code,403)
            ctx.exception.close()
            server.shutdown()
            server.server_close()

    def test_two_mainline_generations_cannot_overlap_even_when_resuming(self):
        from guided_learning.web import LearningApp
        from guided_learning.store import OperationError
        class BlockingRunner:
            def run(self,prompt,cwd,emit,cancel): cancel.wait(3)
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Quantum'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'state','title':'States'}],'route':['state'],'coverage':[]})
            app=LearningApp(tmp,runner=BlockingRunner())
            try:
                app.start_turn({'id':'old','concept_id':'state','prompt':'Lesson'})
                app.pause_turn('old');app.wait('old',2)
                app.start_turn({'id':'new','concept_id':'state','prompt':'Other lesson'})
                with self.assertRaises(OperationError): app.resume_turn('old','r1')
            finally: app.close()

    def test_second_host_cannot_mark_a_live_host_interrupted(self):
        from guided_learning.web import LearningApp
        from guided_learning.store import OperationError
        class BlockingRunner:
            def run(self,prompt,cwd,emit,cancel): cancel.wait(3)
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Quantum'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'state','title':'States'}],'route':['state'],'coverage':[]})
            app=LearningApp(tmp,runner=BlockingRunner())
            try:
                app.start_turn({'id':'one','concept_id':'state','prompt':'Lesson'})
                with self.assertRaises(OperationError): LearningApp(tmp,runner=BlockingRunner())
                self.assertEqual(app.operation({'op':'stream.read','id':'one'})['turn']['status'],'running')
            finally: app.close()

    def test_cross_origin_posts_consistently_receive_403_without_applying_operations(self):
        from guided_learning.web import create_server
        from http.client import HTTPConnection
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Quantum'})
            server=create_server(tmp,port=0)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                for _ in range(20):
                    connection=HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                    try:
                        connection.request('POST','/api/operation',json.dumps({'op':'course.init','title':'x'*65536}),
                                           {'Content-Type':'application/json','Origin':'https://evil.example'})
                        response=connection.getresponse()
                        self.assertEqual(response.status,403)
                        self.assertEqual(json.loads(response.read())['error'],'Invalid local origin')
                    finally: connection.close()
                self.assertEqual(server.app.snapshot()['course']['title'],'Quantum')
            finally:
                server.shutdown();server.server_close()
