import json
import sys
import tempfile
import threading
import time
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
   {'method':'thread/tokenUsage/updated','params':{'threadId':'t','turnId':'u','tokenUsage':{'last':{'inputTokens':100,'cachedInputTokens':60,'outputTokens':5,'reasoningOutputTokens':1,'totalTokens':105},'total':{}}}},
   {'method':'item/started','params':{'threadId':'t','turnId':'u','item':{'id':'a','type':'agentMessage','phase':'final_answer'}}},
   {'method':'item/agentMessage/delta','params':{'threadId':'t','turnId':'u','itemId':'a','delta':'Hello lesson'}},
   {'method':'thread/tokenUsage/updated','params':{'threadId':'t','turnId':'u','tokenUsage':{'last':{'inputTokens':120,'cachedInputTokens':100,'outputTokens':9,'reasoningOutputTokens':2,'totalTokens':129},'total':{}}}},
   {'method':'item/completed','params':{'threadId':'t','turnId':'u','item':{'id':'a','type':'agentMessage','phase':'final_answer','text':'Hello lesson.'}}},
   {'method':'turn/completed','params':{'threadId':'t','turn':{'id':'u','status':'completed'}}}]
  for e in events: print(json.dumps(e),flush=True)
''',encoding='utf-8')
            events=[]
            CodexRunner(command=[sys.executable,str(script)]).run('teach',tmp,events.append,threading.Event())
            self.assertEqual(events,[{'kind':'delta','text':'Hello lesson'},{'kind':'final','text':'Hello lesson.'},
                                     {'kind':'complete','usage':{'inputTokens':220,'cachedInputTokens':160,'outputTokens':14,'reasoningOutputTokens':3,'totalTokens':234}}])

    def test_model_list_follows_pages_and_hides_hidden_models(self):
        from guided_learning.codex import list_models
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'server.py'
            script.write_text('''import sys,json
pages={None:{'data':[{'id':'a','displayName':'A','isDefault':True,'supportedReasoningEfforts':[{'reasoningEffort':'low'}],
                      'serviceTiers':[{'id':'priority','name':'Fast','description':'2x speed'}]},
                     {'id':'secret','hidden':True}],'nextCursor':'p2'},
       'p2':{'data':[{'id':'b','description':'Small'}],'nextCursor':None}}
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); i=r.get('id')
 if m=='initialize': print(json.dumps({'id':i,'result':{}}),flush=True)
 if m=='model/list': print(json.dumps({'id':i,'result':pages[r['params'].get('cursor')]}),flush=True)
''',encoding='utf-8')
            self.assertEqual(list_models(command=[sys.executable,str(script)]), [
                {'id':'a','name':'A','description':'','default':True,'efforts':['low'],
                 'tiers':[{'id':'priority','name':'Fast','description':'2x speed'}]},
                {'id':'b','name':'b','description':'Small','default':False,'efforts':[],'tiers':[]}])

    def test_service_tier_is_sent_when_starting_the_thread(self):
        from guided_learning.codex import CodexRunner
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'server.py'
            seen=Path(tmp)/'thread.json'
            script.write_text('''import sys,json
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); i=r.get('id')
 if m=='initialize': print(json.dumps({'id':i,'result':{}}),flush=True)
 if m=='thread/start':
  open(%r,'w').write(json.dumps(r['params'])); sys.exit(0)
''' % str(seen),encoding='utf-8')
            with self.assertRaises(RuntimeError):
                CodexRunner(command=[sys.executable,str(script)],service_tier='priority').run('teach',tmp,lambda e:None,threading.Event())
            self.assertEqual(json.loads(seen.read_text())['serviceTier'],'priority')

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


class FindCodex(unittest.TestCase):
    def test_explicit_path_then_path_then_desktop_app(self):
        from unittest import mock
        from guided_learning import codex
        with tempfile.TemporaryDirectory() as tmp:
            bundled = Path(tmp) / 'OpenAI' / 'Codex' / 'bin' / 'codex.exe'
            bundled.parent.mkdir(parents=True)
            bundled.write_text('')
            with mock.patch.dict(codex.os.environ, {'CODEX_CLI_PATH': '/opt/codex'}):
                self.assertEqual(codex.find_codex(), '/opt/codex')
            with mock.patch.dict(codex.os.environ, {'LOCALAPPDATA': tmp}), mock.patch.object(codex.shutil, 'which', return_value='/usr/bin/codex'):
                codex.os.environ.pop('CODEX_CLI_PATH', None)
                self.assertEqual(codex.find_codex(), '/usr/bin/codex')
            with mock.patch.dict(codex.os.environ, {'LOCALAPPDATA': tmp}), mock.patch.object(codex.shutil, 'which', return_value=None):
                codex.os.environ.pop('CODEX_CLI_PATH', None)
                self.assertEqual(codex.find_codex(), str(bundled))


SAVED_SERVER = '''import sys,json
log=open(%r,'a'); mode=%r
def out(v): print(json.dumps(v),flush=True)
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); i=r.get('id'); p=r.get('params',{})
 if m: log.write(json.dumps([m,p])+'\\n'); log.flush()
 if m=='initialize': out({'id':i,'result':{}})
 if m=='thread/list': out({'id':i,'result':{'data':[{'id':'old','originator':'guided_learning','createdAt':0}]*2 if p.get('archived') else []}})
 if m=='thread/archive': out({'id':i,'result':{}})
 if m=='thread/unarchive':
  out({'id':i,'error':{'code':-32600,'message':'no rollout'}} if mode=='lost' else {'id':i,'result':{}})
 if m=='thread/delete': out({'id':i,'result':{}})
 if m=='thread/start': out({'id':i,'result':{'thread':{'id':'new'}}})
 if m=='thread/resume':
  out({'id':i,'error':{'code':-32600,'message':'no rollout'}} if mode=='lost' else {'id':i,'result':{'thread':{'id':p['threadId']}}})
 if m=='thread/revert':
  out({'id':i,'error':{'code':-32601,'message':'unknown method'}} if mode=='old' else {'id':i,'result':{}})
 if m=='turn/start':
  t=p['threadId']
  for e in [{'id':i,'result':{'turn':{'id':'u'}}},
   {'method':'item/started','params':{'threadId':t,'turnId':'u','item':{'id':'a','type':'agentMessage','phase':'final_answer'}}},
   {'method':'item/completed','params':{'threadId':t,'turnId':'u','item':{'id':'a','type':'agentMessage','phase':'final_answer','text':'Lesson.'}}},
   {'method':'turn/completed','params':{'threadId':t,'turn':{'id':'u','status':'completed'}}}]: out(e)
'''


class SavedThreads(unittest.TestCase):
    """Teaching prompts run in saved threads lent for one turn and reverted and archived after it, so the prompt cache
    is reused and idle threads stay out of the learner's Codex session list."""

    def setUp(self):
        from guided_learning import codex
        self.codex = codex
        self.addCleanup(setattr, codex, 'THREADS', codex.THREADS)
        codex.THREADS = codex.SavedThreads()

    def turns(self, tmp, prompts, mode='ok'):
        log = Path(tmp)/'calls.jsonl'
        script = Path(tmp)/'server.py'
        script.write_text(SAVED_SERVER % (str(log), mode), encoding='utf-8')
        runner = self.codex.CodexRunner(command=[sys.executable, str(script)], model='m')
        for prompt in prompts:
            events = []
            runner.run(prompt, tmp, events.append, threading.Event())
            self.assertEqual(events[-1], {'kind':'complete'})
        return [json.loads(line) for line in log.read_text().splitlines()]

    def teaching(self, request):
        from guided_learning.server.prompts import Prompt
        return Prompt('Teacher instructions and route', request)

    def test_a_teaching_turn_is_reverted_and_the_next_one_resumes_its_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.turns(tmp, [self.teaching('Teach step 1'), self.teaching('Teach step 2')])
            threads = [p for m, p in calls if m in ('thread/start', 'thread/resume')]
            lending = ('thread/start', 'thread/unarchive', 'thread/resume', 'thread/revert', 'thread/archive')
            self.assertEqual([m for m, _ in calls if m in lending],
                             ['thread/start', 'thread/revert', 'thread/archive',
                              'thread/unarchive', 'thread/resume', 'thread/revert', 'thread/archive'])
            self.assertEqual({p['threadId'] for m, p in calls if m in ('thread/archive', 'thread/unarchive')}, {'new'})
            self.assertFalse(threads[0]['ephemeral'])
            self.assertEqual((threads[1]['threadId'], threads[1]['excludeTurns']), ('new', True))
            self.assertEqual({p['developerInstructions'] for p in threads}, {'Teacher instructions and route'})
            self.assertEqual([p['input'][0]['text'] for m, p in calls if m == 'turn/start'], ['Teach step 1', 'Teach step 2'])
            self.assertEqual([p['beforeTurnId'] for m, p in calls if m == 'thread/revert'], ['u', 'u'])

    def test_a_lost_thread_is_replaced_and_plain_prompts_stay_ephemeral(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.turns(tmp, [self.teaching('one'), self.teaching('two'), 'Build the chapter'], mode='lost')
            starts = [(m, p.get('ephemeral'), 'developerInstructions' in p) for m, p in calls if m in ('thread/start', 'thread/resume')]
            self.assertEqual(starts, [('thread/start', False, True), ('thread/resume', None, True),
                                      ('thread/start', False, True), ('thread/start', True, False)])
            self.assertEqual(sum(m == 'thread/revert' for m, _ in calls), 2)

    def test_a_codex_that_cannot_revert_gets_ephemeral_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.turns(tmp, [self.teaching('one'), self.teaching('two')], mode='old')
            self.assertEqual([(m, p.get('ephemeral')) for m, p in calls if m in ('thread/start', 'thread/resume')],
                             [('thread/start', False), ('thread/start', True)])
            self.assertFalse(self.codex.THREADS.enabled)

    def test_closing_a_course_deletes_its_idle_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.turns(tmp, [self.teaching('one')])
            self.codex.THREADS.close(tmp, [sys.executable, str(Path(tmp)/'server.py')])
            calls = [json.loads(line) for line in (Path(tmp)/'calls.jsonl').read_text().splitlines()]
            self.assertIn(['thread/delete', {'threadId': 'new'}], calls)
            self.assertEqual(self.codex.THREADS.idle, {})

    def test_the_first_turn_in_a_folder_deletes_threads_an_earlier_run_left_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.turns(tmp, [self.teaching('one')])
            log = Path(tmp)/'calls.jsonl'
            for _ in range(50):
                calls = [json.loads(line) for line in log.read_text().splitlines()]
                if ['thread/delete', {'threadId': 'old'}] in calls: break
                time.sleep(.1)
            self.assertEqual([p.get('archived') for m, p in calls if m == 'thread/list'], [False, True])
            self.assertEqual(calls.count(['thread/delete', {'threadId': 'old'}]), 1)
