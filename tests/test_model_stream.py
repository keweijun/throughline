import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

class ModelStream(unittest.TestCase):
    def test_streams_final_phase_and_requires_successful_turn(self):
        from guided_learning.model_stream import CodexRunner
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'server.py'
            script.write_text('''import sys,json
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); i=r.get('id')
 if m=='initialize': print(json.dumps({'id':i,'result':{}}),flush=True)
 if m=='thread/start': print(json.dumps({'id':i,'result':{'thread':{'id':'t'}}}),flush=True)
 if m=='turn/start':
  events=[{'id':i,'result':{'turn':{'id':'u'}}},
   {'method':'turn/started','params':{'threadId':'t','turn':{'id':'u'}}},
   {'method':'item/started','params':{'threadId':'t','turnId':'u','item':{'id':'c','type':'agentMessage','phase':'commentary'}}},
   {'method':'item/agentMessage/delta','params':{'threadId':'t','turnId':'u','itemId':'c','delta':'Not a lesson'}},
   {'method':'item/started','params':{'threadId':'t','turnId':'u','item':{'id':'a','type':'agentMessage','phase':'final_answer'}}},
   {'method':'item/agentMessage/delta','params':{'threadId':'t','turnId':'u','itemId':'a','delta':'Hello lesson'}},
   {'method':'item/completed','params':{'threadId':'t','turnId':'u','item':{'id':'a','type':'agentMessage','phase':'final_answer','text':'Hello lesson.'}}},
   {'method':'turn/completed','params':{'threadId':'t','turn':{'id':'u','status':'completed'}}}]
  for e in events: print(json.dumps(e),flush=True)
''',encoding='utf-8')
            events=[]
            CodexRunner(command=[sys.executable,str(script)]).run('teach',tmp,events.append,threading.Event())
            self.assertEqual(events,[{'kind':'delta','text':'Hello lesson'},{'kind':'final','text':'Hello lesson.'},{'kind':'complete'}])
