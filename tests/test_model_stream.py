import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

class ModelStream(unittest.TestCase):
    def test_streams_final_phase_and_requires_successful_turn(self):
        from guided_learning.codex import CodexRunner
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

    def test_commentary_only_and_connection_loss_never_complete_a_lesson(self):
        from guided_learning.codex import CodexRunner
        for terminal in ('completed','disconnect'):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory() as tmp:
                script=Path(tmp)/'server.py'
                script.write_text('''import sys,json
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); i=r.get('id')
 if m=='initialize': print(json.dumps({'id':i,'result':{}}),flush=True)
 if m=='thread/start': print(json.dumps({'id':i,'result':{'thread':{'id':'t'}}}),flush=True)
 if m=='turn/start':
  print(json.dumps({'id':i,'result':{'turn':{'id':'u'}}}),flush=True)
  print(json.dumps({'method':'item/completed','params':{'threadId':'t','turnId':'u','item':{'id':'c','type':'agentMessage','phase':'commentary','text':'Working'}}}),flush=True)
''' + ("  print(json.dumps({'method':'turn/completed','params':{'threadId':'t','turn':{'id':'u','status':'completed'}}}),flush=True)\n" if terminal=='completed' else '  sys.exit(0)\n'),encoding='utf-8')
                events=[]
                with self.assertRaises(RuntimeError):
                    CodexRunner(command=[sys.executable,str(script)]).run('teach',tmp,events.append,threading.Event())
                self.assertEqual(events,[])

    def test_cancel_stalled_handshake_terminates_owned_process_promptly(self):
        import time
        from unittest.mock import patch
        import subprocess
        from guided_learning.codex import CodexRunner
        for stalled in ('initialize','thread/start','turn/start'):
            with self.subTest(stalled=stalled), tempfile.TemporaryDirectory() as tmp:
                script=Path(tmp)/'server.py'
                script.write_text("import sys,json,time\nfor line in sys.stdin:\n r=json.loads(line); m=r.get('method'); i=r.get('id')\n if m=="+repr(stalled)+": time.sleep(60)\n if m=='initialize': print(json.dumps({'id':i,'result':{}}),flush=True)\n if m=='thread/start': print(json.dumps({'id':i,'result':{'thread':{'id':'t'}}}),flush=True)\n",encoding='utf-8')
                cancel=threading.Event(); timer=threading.Timer(.3,cancel.set); timer.start()
                owned=[]; real_popen=subprocess.Popen
                def launch(*args,**kwargs):
                    process=real_popen(*args,**kwargs);owned.append(process);return process
                started=time.monotonic()
                try:
                    with patch('guided_learning.codex.subprocess.Popen',side_effect=launch):
                        CodexRunner(command=[sys.executable,str(script)],timeout=2).run('teach',tmp,lambda e:None,cancel)
                    self.assertLess(time.monotonic()-started,1.5)
                    self.assertIsNotNone(owned[0].poll())
                finally:timer.cancel()
