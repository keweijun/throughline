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
            self.assertIn('来源',runner.prompt)
            with self.assertRaises(HTTPError) as ctx:
                post('/api/turns',{'id':'evil','concept_id':'state','prompt':'x'},'https://evil.example')
            self.assertEqual(ctx.exception.code,403)
            ctx.exception.close()
            server.shutdown()
            server.server_close()
