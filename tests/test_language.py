import tempfile
import time
import unittest
from guided_learning.api import execute
from guided_learning.store import OperationError, Store
from guided_learning.server import Host
from tests.support import host_client


class LanguagePreferences(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=self.tmp.name
        self.op(op='course.init',title='Physics')
        self.op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])

    def tearDown(self):
        self.tmp.cleanup()

    def op(self,**request):
        return execute(self.path,request)

    def test_default_persistence_validation_and_evidence_isolation(self):
        self.assertEqual(self.op(op='preferences.view')['preferences'],{'language':'en'})
        before=self.op(op='session.resume')
        self.op(op='preferences.save',language='zh-CN')
        self.assertEqual(execute(self.path,{'op':'preferences.view'})['preferences']['language'],'zh-CN')
        for invalid in ('fr',None,[],{},12):
            with self.assertRaises(OperationError):self.op(op='preferences.save',language=invalid)
        self.assertEqual(self.op(op='preferences.view')['preferences']['language'],'zh-CN')
        self.assertEqual(self.op(op='session.resume'),before)
        self.assertFalse(self.op(op='evidence.view',concept_id='a')['independently_verified'])

    def test_a_daily_review_limit_saved_before_review_was_asked_for_is_not_a_preference(self):
        # Review had a daily limit before ADR 0014; a course still storing one reads the language only.
        store=Store(self.path)
        with store.db:
            store.put('course','preferences',{'language':'zh-CN','daily_reviews':8})
        store.db.close()
        self.assertEqual(self.op(op='preferences.view')['preferences'],{'language':'zh-CN'})
        with self.assertRaises(OperationError):self.op(op='preferences.save',daily_reviews=5)
        with self.assertRaises(OperationError):self.op(op='preferences.save')

    def test_running_turns_are_frozen_and_retries_do_not_change_language(self):
        request={'op':'stream.start','id':'one','concept_id':'a','prompt':'Explain','channel':'sidequestion'}
        first=self.op(**request)['turn']
        self.op(op='preferences.save',language='zh-CN')
        retry=self.op(**request)
        self.assertFalse(retry['created']);self.assertEqual(retry['turn']['language'],'en')
        self.assertEqual(retry['turn']['prompt_snapshot'],first['prompt_snapshot'])
        second=self.op(**{**request,'id':'two'})['turn']
        self.assertEqual(second['language'],'zh-CN')
        with self.assertRaises(OperationError):self.op(**{**request,'language':'zh-CN'})
        self.op(op='stream.pause',id='one')
        resumed=self.op(op='stream.resume',id='one',request_id='regenerate')['turn']
        self.assertEqual(resumed['language'],'zh-CN')
        self.assertEqual(resumed['attempts'][0]['language'],'en')
        self.assertEqual(resumed['attempts'][0]['prompt_snapshot'],first['prompt_snapshot'])
        self.assertEqual(resumed['prompt_snapshot']['context'],first['prompt_snapshot']['context'])
        self.op(op='preferences.save',language='en')
        self.assertEqual(self.op(op='stream.resume',id='one',request_id='regenerate')['turn']['language'],'zh-CN')

    def test_language_change_invalidates_preparation(self):
        self.op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
        self.op(op='preparation.enqueue',id='prep')
        self.op(op='stream.start',id='prep',concept_id='b',prompt='Internal prep',channel='preparation',record_user=False)
        self.op(op='stream.event',id='prep',attempt=1,sequence=1,kind='final',text='English preparation')
        self.op(op='stream.event',id='prep',attempt=1,sequence=2,kind='complete')
        self.assertIsNotNone(self.op(op='preparation.view',concept_id='b')['ready'])
        self.op(op='preferences.save',language='zh-CN')
        changed=self.op(op='preparation.view',concept_id='b')
        self.assertIsNone(changed['ready']);self.assertEqual(changed['jobs'][0]['status'],'stale')
        self.assertEqual(self.op(op='preparation.enqueue',id='prep-zh')['job']['snapshot']['language'],'zh-CN')

    def test_http_language_selection_reaches_teacher_and_survives_reopen(self):
        import threading
        class Runner:
            def __init__(self):
                self.prompts=[]
                self.received=threading.Event()
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt)
                self.received.set()
                cancel.wait(3)
        runner=Runner()
        client,host=host_client(self.path,runner=runner)
        with client:
            self.assertEqual(client.get('/api/state').json()['preferences']['language'],'en')
            self.assertEqual(client.put('/api/preferences',json={'language':'zh-CN'}).status_code,200)
            self.assertEqual(client.put('/api/preferences',json={'language':'xx'}).status_code,400)
            self.assertEqual(client.put('/api/preferences',json={'daily_reviews':3}).status_code,400)
            turn=client.post('/api/lessons',json={'id':'lesson'}).json()['turn']
            self.assertTrue(runner.received.wait(2))
            self.assertEqual(turn['language'],'zh-CN')
            self.assertIn('selected teaching language: Simplified Chinese',runner.prompts[0])
            self.assertIn('## 章节导览',runner.prompts[0])
            self.assertIn('JSON field names/enumerated values unchanged',runner.prompts[0])
            client.put('/api/preferences',json={'language':'en'})
            self.assertEqual(self.op(op='stream.read',id='lesson')['turn']['language'],'zh-CN')
            client.put('/api/preferences',json={'language':'zh-CN'})
        reopened,host=host_client(self.path,runner=Runner())
        with reopened:
            self.assertEqual(reopened.get('/api/state').json()['preferences']['language'],'zh-CN')
            self.assertFalse(self.op(op='evidence.view',concept_id='a')['independently_verified'])


    def test_failure_in_previous_language_does_not_block_new_preparation(self):
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                if 'selected teaching language: English' in prompt:raise RuntimeError('Synthetic English failure')
                emit({'kind':'final','text':'Chinese preparation'});emit({'kind':'complete'})
        self.op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
        app=Host(self.path,runner=Runner())
        try:
            def wait_for(status):
                deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    jobs=self.op(op='preparation.view',concept_id='b')['jobs']
                    if any(j['status']==status for j in jobs):return jobs
                    time.sleep(.03)
                self.fail('Preparation did not become '+status)
            wait_for('failed')
            self.op(op='preferences.save',language='zh-CN')
            jobs=wait_for('ready')
            self.assertEqual(next(j for j in jobs if j['status']=='ready')['snapshot']['language'],'zh-CN')
        finally:app.close()
