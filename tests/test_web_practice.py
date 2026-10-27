import tempfile
import unittest
from guided_learning.api import execute
from guided_learning.server import Host


def practice_call(app,endpoint,body):
    if endpoint=='generate': return app.practice.generate(body['concept_id'])
    if endpoint=='next': return app.practice.next_section(body['concept_id'],body['request_id'])
    return app.practice.act(body['id'],body['action'],body.get('answer'))

class PracticeFlow(unittest.TestCase):
    def test_generation_asks_for_each_part_on_its_own_line(self):
        class Runner:
            prompts=[]
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt)
                emit({'kind':'final','text':'{"questions":[{"question":"Two parts:\\n1. First\\n2. Second","origin":"self_created","source_refs":[]}]}'})
                emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'light','title':'Light'}],'route':['light'],'coverage':[]})
            runner=Runner();app=Host(path,runner=runner)
            app.wait(app.practice.generate('light')['turn']['id'],5)
            prompt=next(p for p in runner.prompts if 'Practice only' in p)
            self.assertIn('numbered list',prompt)
            self.assertIn('own line',prompt)
            self.assertEqual(app.practice.state()['tasks'][0]['question'],'Two parts:\n1. First\n2. Second')
            app.close()

    def test_questions_survive_restart_without_solution_or_mastery(self):
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                emit({'kind':'final','text':'{"questions":[{"question":"Explain why doubling intensity does not double electron energy.","origin":"self_created","source_refs":[]}]}'})
                emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'light','title':'Light'}],'route':['light'],'coverage':[]})
            app=Host(path,runner=Runner())
            result=app.practice.generate('light')
            app.wait(result['turn']['id'],5)
            state=app.practice.state()
            self.assertEqual(len(state['tasks']),1)
            self.assertIn('doubling',state['tasks'][0]['question'])
            self.assertNotIn('solution',state['tasks'][0])
            self.assertTrue(all(i['role']=='assistant' for i in app.snapshot()['session']['recent_interactions']))
            self.assertFalse(execute(path,{'op':'evidence.view','concept_id':'light'})['independently_verified'])
            app.close()
            reopened=Host(path,runner=Runner())
            self.assertEqual(reopened.practice.state()['tasks'],state['tasks'])
            reopened.close()

    def test_assessment_uses_teacher_outcome_and_preserves_assistance_provenance(self):
        class Runner:
            reply=''
            def run(self,prompt,cwd,emit,cancel):
                emit({'kind':'final','text':self.reply}); emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'},{'id':'b','title':'B'}],'route':['a','b'],'coverage':[]})
            runner=Runner(); app=Host(path,runner=runner)
            def call(action,body,reply):
                runner.reply=reply
                result=practice_call(app,action,body)
                if 'turn' in result: app.wait(result['turn']['id'],5)
                return app.practice.state()
            state=call('generate',{'concept_id':'a'},'{"questions":[{"question":"What is 2+2?","origin":"self_created","source_refs":[]}]}')
            tid=state['tasks'][0]['id']
            state=call('action',{'id':tid,'action':'assess','answer':'wrong'},'{"feedback":"Incorrect: add both pairs.","outcome":"needs_work"}')
            self.assertEqual(state['tasks'][0]['history'][-1]['outcome'],'needs_work')
            self.assertFalse(execute(path,{'op':'evidence.view','concept_id':'a'})['independently_verified'])
            call('action',{'id':tid,'action':'solution'},'{"feedback":"2+2=4."}')
            state=call('action',{'id':tid,'action':'assess','answer':'4'},'{"feedback":"Correct.","outcome":"passed"}')
            self.assertEqual(state['tasks'][0]['history'][-1]['kind'],'hinted')
            self.assertFalse(execute(path,{'op':'evidence.view','concept_id':'a'})['independently_verified'])
            state=call('action',{'id':tid,'action':'assess','answer':'4'},'{"feedback":"looks fine"}')
            self.assertIn('error',state['jobs'][-1] if 'error' in state['jobs'][-1] else next(j for j in state['jobs'] if 'error' in j))
            app.practice.act(tid,'defer')
            result=app.practice.next_section('a','next')
            self.assertEqual(result['position']['concept_id'],'b')
            self.assertEqual(app.practice.state()['tasks'][0]['status'],'deferred')
            app.close()

    def test_defer_cancels_late_assessment_without_losing_pending_task(self):
        import threading
        class Runner:
            gate=threading.Event()
            assessment=False
            def run(self,prompt,cwd,emit,cancel):
                if self.assessment:
                    self.gate.wait(3)
                    reply='{"feedback":"Correct","outcome":"passed"}'
                else: reply='{"questions":[{"question":"Explain energy conservation.","origin":"self_created","source_refs":[]}]}'
                emit({'kind':'final','text':reply});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
            runner=Runner();app=Host(path,runner=runner)
            turn=app.practice.generate('a')['turn'];app.wait(turn['id'],5)
            task=app.practice.state()['tasks'][0]
            runner.assessment=True
            turn=app.practice.act(task['id'],'assess','Energy is conserved.')['turn']
            app.practice.act(task['id'],'defer')
            runner.gate.set();app.wait(turn['id'],5)
            self.assertEqual(app.practice.state()['tasks'][0]['status'],'deferred')
            self.assertFalse(execute(path,{'op':'evidence.view','concept_id':'a'})['independently_verified'])
            app.close()

    def test_original_exercise_reference_with_metadata_is_supported(self):
        import json
        from pathlib import Path
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                self.prompt=prompt
                emit({'kind':'final','text':json.dumps({'questions':[{'question':'Compute photon energy.','origin':'source','source_refs':[ref]}]})});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            file=Path(path)/'exercise.md';file.write_text('Compute photon energy. Answer: E=hf.',encoding='utf-8')
            source=execute(path,{'op':'source.register','path':str(file)})['source']
            ref={'source_id':source['id'],'revision':source['revision'],'unit_id':'line-1'}
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'Photons','exercises':[{**ref,'question':'1(a)'}]}],'route':['a'],'coverage':[]})
            runner=Runner();app=Host(path,runner=runner)
            turn=app.practice.generate('a')['turn'];app.wait(turn['id'],5)
            state=app.practice.state()
            self.assertEqual(len(state['tasks']),1)
            self.assertEqual(state['tasks'][0]['source_refs'],[ref])
            self.assertNotIn('E=hf',state['tasks'][0]['question'])
            self.assertIn('Answer: E=hf',runner.prompt)
            app.close()

    def test_correction_feedback_counts_as_help_on_a_retry(self):
        class Runner:
            reply=''
            def run(self,prompt,cwd,emit,cancel):
                emit({'kind':'final','text':self.reply});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
            runner=Runner();app=Host(path,runner=runner)
            def run(endpoint,body,text):
                runner.reply=text;r=practice_call(app,endpoint,body);t=app.wait(r['turn']['id'],5);self.assertEqual(t['status'],'completed',t)
                return app.practice.state()
            s=run('generate',{'concept_id':'a'},'{"questions":[{"question":"2+2?","origin":"self_created","source_refs":[]}]}');self.assertTrue(s['tasks'], s);tid=s['tasks'][0]['id']
            run('action',{'id':tid,'action':'assess','answer':'5'},'{"feedback":"No: 2+2=4.","outcome":"needs_work"}')
            s=run('action',{'id':tid,'action':'assess','answer':'4'},'{"feedback":"Correct.","outcome":"passed"}')
            self.assertEqual(s['tasks'][0]['history'][-1]['kind'],'hinted')
            app.close()



    def test_closed_host_rejects_new_model_work(self):
        from guided_learning.store import OperationError
        class Runner:
            def run(self,*args):raise AssertionError('closed host must never call model')
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
            app=Host(path,runner=Runner());app.close()
            with self.assertRaises(OperationError) as result:
                app.start_turn({'concept_id':'a','prompt':'Explain','channel':'mainline'})
            self.assertEqual(result.exception.code,'host_closing')
