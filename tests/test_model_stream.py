import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

class ModelStream(unittest.TestCase):
    def test_streams_final_phase_and_requires_successful_turn(self):
        from throughline.codex import CodexRunner
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
        from throughline.codex import list_models
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
        from throughline.codex import CodexRunner
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
        from throughline.codex import CodexRunner
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
        from throughline.codex import CodexRunner
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
                    with patch('throughline.codex.subprocess.Popen',side_effect=launch):
                        CodexRunner(command=[sys.executable,str(script)],timeout=2).run('teach',tmp,lambda e:None,cancel)
                    self.assertLess(time.monotonic()-started,1.5)
                    self.assertIsNotNone(owned[0].poll())
                finally:timer.cancel()


class FindCodex(unittest.TestCase):
    def test_explicit_path_then_path_then_desktop_app(self):
        from unittest import mock
        from throughline import codex
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(codex.os.environ, {'THROUGHLINE_CONFIG': str(Path(tmp) / 's.json')}):
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


class SavedCodex(unittest.TestCase):
    """A host the macOS launcher starts from Finder or Spotlight has no shell PATH: setup's saved codex stands in."""

    def setUp(self):
        from unittest import mock
        from throughline import codex
        self.codex = codex
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.cli = self.home / 'npm' / 'bin' / ('codex.exe' if os.name == 'nt' else 'codex')
        self.cli.parent.mkdir(parents=True)
        self.cli.write_text('')
        self.cli.chmod(0o755)
        self.settings = self.home / 'config' / 'settings.json'
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({'model': 'gpt-6-luna', 'future_key': 1}), encoding='utf-8')
        self.app = self.home / 'OpenAI' / 'Codex' / 'bin' / 'codex.exe'  # the desktop app's copy, the last resort
        self.app.parent.mkdir(parents=True)
        self.app.write_text('')
        environment = mock.patch.dict(codex.os.environ, {'THROUGHLINE_CONFIG': str(self.settings), 'LOCALAPPDATA': str(self.home),
                                                         'PATH': str(self.cli.parent)})
        environment.start()
        self.addCleanup(environment.stop)
        codex.os.environ.pop('CODEX_CLI_PATH', None)

    def assertSamePath(self, found, expected):
        self.assertEqual(os.path.normcase(str(found)), os.path.normcase(str(expected)))  # Windows' which upper-cases .EXE

    def launcher_environment(self):
        """What a host started by the launcher sees: a PATH without the folder codex is in."""
        self.codex.os.environ['PATH'] = str(self.home / 'system')

    def test_setup_saves_codex_and_a_launcher_started_host_finds_it(self):
        self.assertSamePath(self.codex.remember_codex(), self.cli)
        saved = json.loads(self.settings.read_text(encoding='utf-8'))
        self.assertSamePath(saved.pop('codex_path'), self.cli)
        self.assertEqual(saved.pop('codex_path_dirs'), [], 'an empty file is no Node script')
        self.assertEqual(saved, {'model': 'gpt-6-luna', 'future_key': 1}, 'the settings and keys it does not know stay')
        self.launcher_environment()
        self.assertSamePath(self.codex.find_codex(), self.cli)
        env = self.codex.codex_env(self.codex.find_codex())
        self.assertIn(str(self.cli.parent), env['PATH'].split(os.pathsep), 'so an npm codex finds its node')
        self.assertEqual(self.codex.os.environ['PATH'], str(self.home / 'system'), "the host's own PATH stays as it was")

    def test_a_running_host_finds_a_codex_setup_saved_after_it_started(self):
        self.codex.remember_codex()
        self.launcher_environment()
        self.assertSamePath(self.codex.find_codex(), self.cli)
        # Then setup, run again in another terminal, saves another codex.
        moved = self.home / 'moved' / self.cli.name
        moved.parent.mkdir()
        moved.write_text('')
        moved.chmod(0o755)
        from throughline.userfiles import write_json
        write_json(self.settings, {'codex_path': str(moved), 'codex_path_dirs': []})
        self.assertSamePath(self.codex.find_codex(), moved)

    @unittest.skipIf(os.name == 'nt', 'a POSIX script with a #!/usr/bin/env node line')
    def test_an_npm_codex_whose_node_is_in_another_folder_runs_from_the_launcher(self):
        # npm puts the codex script in its bin folder; nvm, Homebrew or Volta may keep node somewhere else.
        node = self.home / 'node' / 'bin' / 'node'
        node.parent.mkdir(parents=True)
        server = self.home / 'server.py'
        server.write_text(SAVED_SERVER % (str(self.home / 'calls'), 'ok'), encoding='utf-8')
        node.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{server}" "$@"\n')
        node.chmod(0o755)
        self.cli.write_text('#!/usr/bin/env node\nconsole.log("codex")\n')
        self.codex.os.environ['PATH'] = os.pathsep.join([str(self.cli.parent), str(node.parent)])  # setup's terminal
        self.codex.remember_codex()
        self.assertEqual(json.loads(self.settings.read_text(encoding='utf-8'))['codex_path_dirs'], [str(node.parent)])
        self.launcher_environment()
        events = []
        with tempfile.TemporaryDirectory() as cwd:
            self.codex.CodexRunner(model='m').run('Say hello', cwd, events.append, threading.Event())
        self.assertEqual(events[-2:], [{'kind': 'final', 'text': 'Lesson.'}, {'kind': 'complete'}])
        self.assertEqual(self.codex.os.environ['PATH'], str(self.home / 'system'))

    def test_setup_saves_no_node_folder_for_a_codex_that_is_not_a_node_script(self):
        self.cli.write_bytes(b'\x7fELF binary')
        self.codex.remember_codex()
        self.assertEqual(json.loads(self.settings.read_text(encoding='utf-8'))['codex_path_dirs'], [])

    def test_path_and_the_explicit_override_come_before_the_saved_codex(self):
        self.codex.remember_codex()
        other = self.home / 'brew' / self.cli.name
        other.parent.mkdir()
        other.write_text('')
        other.chmod(0o755)
        self.codex.os.environ['PATH'] = str(other.parent)
        self.assertSamePath(self.codex.find_codex(), other)
        self.codex.os.environ['CODEX_CLI_PATH'] = '/opt/codex'
        self.assertEqual(self.codex.find_codex(), '/opt/codex')

    def test_a_saved_codex_that_is_gone_is_ignored(self):
        self.codex.remember_codex()
        self.cli.unlink()
        self.launcher_environment()
        self.assertSamePath(self.codex.find_codex(), self.app)

    def test_rerunning_setup_refreshes_the_saved_codex_and_keeps_it_when_codex_is_not_on_path(self):
        self.codex.remember_codex()
        moved = self.home / 'moved' / self.cli.name
        moved.parent.mkdir()
        moved.write_text('')
        moved.chmod(0o755)
        self.codex.os.environ['PATH'] = str(moved.parent)
        self.assertSamePath(self.codex.remember_codex(), moved)
        self.launcher_environment()
        self.assertIsNone(self.codex.remember_codex())
        self.assertSamePath(json.loads(self.settings.read_text(encoding='utf-8'))['codex_path'], moved)
        self.assertSamePath(self.codex.find_codex(), moved)

    def test_teacher_settings_keep_the_saved_codex(self):
        from throughline.server.settings import TeacherSettings
        self.codex.remember_codex()
        TeacherSettings(self.settings).save('gpt-6-sol', 'high')
        self.launcher_environment()
        self.assertSamePath(self.codex.find_codex(), self.cli)

# Each call is its own file: the teaching turn and the thread sweep run servers at once, and Windows does not append atomically.
SAVED_SERVER = '''import sys,json,os,time
log=%r; mode=%r; n=0
os.makedirs(log,exist_ok=True)
def out(v): print(json.dumps(v),flush=True)
for line in sys.stdin:
 r=json.loads(line); m=r.get('method'); i=r.get('id'); p=r.get('params',{})
 if m:
  n+=1; name=os.path.join(log,'%%d-%%d-%%06d'%%(time.time_ns(),os.getpid(),n)); open(name+'.tmp','w').write(json.dumps([m,p])); os.replace(name+'.tmp',name+'.json')
 if m=='initialize': out({'id':i,'result':{}})
 if m=='thread/list': out({'id':i,'result':{'data':[{'id':'old','originator':'throughline','createdAt':0}]*2+[{'id':'older','originator':'guided_learning','createdAt':0},{'id':'theirs','originator':'codex_cli_rs','createdAt':0}] if p.get('archived') else []}})
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
        from throughline import codex
        self.codex = codex
        self.addCleanup(setattr, codex, 'THREADS', codex.THREADS)
        codex.THREADS = codex.SavedThreads()
        # Deleting and sweeping threads run Codex in the background; record those runs so a test can wait for them
        # before it reads the calls, and before its folder is removed while a late one still writes there.
        self.tidying = []
        later = codex.THREADS._later
        def tracked(*args, **kwargs):
            before = set(threading.enumerate())
            later(*args, **kwargs)
            self.tidying += [t for t in threading.enumerate() if t not in before]
        codex.THREADS._later = tracked

    def turns(self, tmp, prompts, mode='ok'):
        script = Path(tmp)/'server.py'
        script.write_text(SAVED_SERVER % (str(Path(tmp)/'calls'), mode), encoding='utf-8')
        runner = self.codex.CodexRunner(command=[sys.executable, str(script)], model='m')
        for prompt in prompts:
            events = []
            runner.run(prompt, tmp, events.append, threading.Event())
            self.assertEqual(events[-1], {'kind':'complete'})
        return self.calls(tmp)

    def calls(self, tmp):
        for t in self.tidying: t.join()
        folder = Path(tmp)/'calls'
        return [json.loads(f.read_text()) for f in sorted(folder.glob('*.json'))] if folder.is_dir() else []

    def teaching(self, request):
        from throughline.server.prompts import Prompt
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
            calls = self.calls(tmp)
            self.assertIn(['thread/delete', {'threadId': 'new'}], calls)
            self.assertEqual(self.codex.THREADS.idle, {})

    def test_the_first_turn_in_a_folder_deletes_threads_an_earlier_run_left_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.turns(tmp, [self.teaching('one')])
            self.assertEqual([p.get('archived') for m, p in calls if m == 'thread/list'], [False, True])
            self.assertEqual(calls.count(['thread/delete', {'threadId': 'old'}]), 1)
            self.assertIn(['thread/delete', {'threadId': 'older'}], calls, 'teaching threads from before 0.66, when the client was guided_learning')
            self.assertNotIn(['thread/delete', {'threadId': 'theirs'}], calls, "the learner's own Codex threads")
