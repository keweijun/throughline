import tempfile
import unittest
from guided_learning.api import execute

class PreparationState(unittest.TestCase):
    def test_preparation_is_internal_and_ready_does_not_change_learning(self):
        with tempfile.TemporaryDirectory() as path:
            def op(**kw): return execute(path,kw)
            op(op='course.init',title='Physics')
            op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            before=op(op='session.resume')
            job=op(op='preparation.enqueue',id='prep')['job']
            self.assertEqual(job['concept_id'],'b')
            op(op='stream.start',id='prep',concept_id='b',prompt='Internal prep',channel='preparation',record_user=False)
            op(op='stream.event',id='prep',attempt=1,sequence=1,kind='final',text='Prepared explanation with uncertainty')
            op(op='stream.event',id='prep',attempt=1,sequence=2,kind='complete')
            op(op='preparation.reconcile')
            ready=op(op='preparation.view',concept_id='b')['ready']
            self.assertEqual(ready['content'],'Prepared explanation with uncertainty')
            self.assertEqual(op(op='session.resume'),before)
            self.assertFalse(op(op='evidence.view',concept_id='b')['independently_verified'])

    def test_route_and_source_changes_discard_material(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as path:
            def op(**kw): return execute(path,kw)
            op(op='course.init',title='Physics')
            file=Path(path)/'notes.md';file.write_text('Old source',encoding='utf8')
            op(op='source.register',path=str(file))
            concepts=[{'id':c,'title':c} for c in 'abc']
            op(op='curriculum.save',concepts=concepts,route=['a','b','c'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            op(op='preparation.enqueue',id='p')
            op(op='stream.start',id='p',concept_id='b',prompt='Internal',channel='preparation',record_user=False)
            file.write_text('New source',encoding='utf8');op(op='source.register',path=str(file))
            op(op='stream.event',id='p',attempt=1,sequence=1,kind='final',text='Stale text')
            op(op='stream.event',id='p',attempt=1,sequence=2,kind='complete')
            state=op(op='preparation.view',concept_id='b')
            self.assertIsNone(state['ready']);self.assertEqual(state['jobs'][0]['status'],'stale')
            op(op='preparation.enqueue',id='p2')
            op(op='curriculum.save',concepts=concepts,route=['a','c','b'],coverage=[],confirm_reorder=True)
            self.assertEqual(op(op='preparation.view')['jobs'][1]['status'],'stale')

    def test_idle_pipeline_preempted_by_foreground_and_ready_is_injected(self):
        import threading
        import time
        from guided_learning.web import LearningApp
        class Runner:
            entered=threading.Event();release=threading.Event();cancelled=threading.Event()
            prompts=[]
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt)
                if '内部备课任务' in prompt:
                    self.entered.set()
                    while not self.release.wait(.01):
                        if cancel.is_set():self.cancelled.set();return
                    text='PREP_UNIQUE: explain with explicit uncertainty'
                else:text='Foreground answer'
                emit({'kind':'final','text':text});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            def op(**kw):return execute(path,kw)
            op(op='course.init',title='Physics');op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            runner=Runner();app=LearningApp(path,runner=runner)
            try:
                self.assertTrue(runner.entered.wait(3),'automatic next-section preparation must start')
                foreground=app.start_turn({'concept_id':'a','channel':'sidequestion','prompt':'Small question'})['turn']
                self.assertEqual(app.wait(foreground['id'],3)['status'],'completed')
                self.assertTrue(runner.cancelled.wait(3))
                runner.release.set()
                deadline=time.time()+4
                while time.time()<deadline:
                    state=app.routes[('GET','/api/preparation')]('')
                    if any(j['status']=='ready' for j in state['jobs']):break
                    time.sleep(.05)
                self.assertTrue(any(j['status']=='ready' for j in state['jobs']))
                op(op='mainline.enter',request_id='next',concept_id='b',goal='B',next_step='explain')
                turn=app.start_turn({'concept_id':'b','channel':'sidequestion','prompt':'Explain'})['turn'];app.wait(turn['id'],3)
                self.assertIn('PREP_UNIQUE',runner.prompts[-1])
                self.assertNotIn('PREP_UNIQUE',str(op(op='session.resume')['recent_interactions']))
            finally:app.close()

    def test_failed_preparation_falls_back_and_shutdown_does_not_schedule(self):
        import time
        from guided_learning.web import LearningApp
        class Runner:
            prompts=[]
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt)
                if '内部备课任务' in prompt:raise RuntimeError('preparation provider unavailable')
                emit({'kind':'final','text':'Teacher fallback'});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            def op(**kw):return execute(path,kw)
            op(op='course.init',title='Physics');op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            runner=Runner();app=LearningApp(path,runner=runner)
            deadline=time.time()+3
            while time.time()<deadline:
                jobs=app.routes[('GET','/api/preparation')]('')['jobs']
                if jobs and jobs[-1]['status']=='failed':break
                time.sleep(.03)
            self.assertEqual(jobs[-1]['status'],'failed')
            time.sleep(.5)
            self.assertEqual(len(app.routes[('GET','/api/preparation')]('')['jobs']),1)
            op(op='mainline.enter',request_id='next',concept_id='b',goal='B',next_step='explain')
            turn=app.start_turn({'concept_id':'b','channel':'sidequestion','prompt':'Explain'})['turn'];self.assertEqual(app.wait(turn['id'],3)['final_text'],'Teacher fallback')
            self.assertIn('自行完成必要来源核对',runner.prompts[-1]);app.close()
            count=len(runner.prompts);time.sleep(.5)
            self.assertEqual(len(runner.prompts),count)
            self.assertFalse(app.routes[('POST','/api/preparation/schedule')]({})['scheduled'])

    def test_orphaned_preparation_recovers_as_failed(self):
        from guided_learning.web import LearningApp
        with tempfile.TemporaryDirectory() as path:
            def op(**kw):return execute(path,kw)
            op(op='course.init',title='Physics');op(op='curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'}],route=['a','b'],coverage=[])
            op(op='mainline.enter',request_id='enter',concept_id='a',goal='A',next_step='explain')
            op(op='preparation.enqueue',id='crashed-before-launch')
            app=LearningApp(path)
            try:self.assertEqual(app.routes[('GET','/api/preparation')]('')['jobs'][0]['status'],'failed')
            finally:app.close()
