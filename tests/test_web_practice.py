import tempfile
import unittest
from guided_learning.api import execute
from guided_learning.web import LearningApp

class PracticeFlow(unittest.TestCase):
    def test_questions_survive_restart_without_solution_or_mastery(self):
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                emit({'kind':'final','text':'{"questions":[{"question":"Explain why doubling intensity does not double electron energy.","origin":"self_created","source_refs":[]}]}'})
                emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'light','title':'Light'}],'route':['light'],'coverage':[]})
            app=LearningApp(path,runner=Runner())
            result=app.routes[('POST','/api/practice/generate')]({'concept_id':'light'})
            app.wait(result['turn']['id'],5)
            state=app.routes[('GET','/api/practice')]('')
            self.assertEqual(len(state['tasks']),1)
            self.assertIn('doubling',state['tasks'][0]['question'])
            self.assertNotIn('solution',state['tasks'][0])
            self.assertFalse(execute(path,{'op':'evidence.view','concept_id':'light'})['independently_verified'])
            app.close()
            reopened=LearningApp(path,runner=Runner())
            self.assertEqual(reopened.routes[('GET','/api/practice')]('')['tasks'],state['tasks'])
            reopened.close()

    def test_assessment_uses_teacher_outcome_and_preserves_assistance_provenance(self):
        class Runner:
            reply=''
            def run(self,prompt,cwd,emit,cancel):
                emit({'kind':'final','text':self.reply}); emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'},{'id':'b','title':'B'}],'route':['a','b'],'coverage':[]})
            runner=Runner(); app=LearningApp(path,runner=runner)
            def call(action,body,reply):
                runner.reply=reply
                result=app.routes[('POST','/api/practice/'+action)](body)
                if 'turn' in result: app.wait(result['turn']['id'],5)
                return app.routes[('GET','/api/practice')]('')
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
            app.routes[('POST','/api/practice/action')]({'id':tid,'action':'defer'})
            result=app.routes[('POST','/api/practice/next')]({'concept_id':'a','request_id':'next'})
            self.assertEqual(result['position']['concept_id'],'b')
            self.assertEqual(app.routes[('GET','/api/practice')]('')['tasks'][0]['status'],'deferred')
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
            runner=Runner();app=LearningApp(path,runner=runner)
            turn=app.routes[('POST','/api/practice/generate')]({'concept_id':'a'})['turn'];app.wait(turn['id'],5)
            task=app.routes[('GET','/api/practice')]('')['tasks'][0]
            runner.assessment=True
            turn=app.routes[('POST','/api/practice/action')]({'id':task['id'],'action':'assess','answer':'Energy is conserved.'})['turn']
            app.routes[('POST','/api/practice/action')]({'id':task['id'],'action':'defer'})
            runner.gate.set();app.wait(turn['id'],5)
            self.assertEqual(app.routes[('GET','/api/practice')]('')['tasks'][0]['status'],'deferred')
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
            runner=Runner();app=LearningApp(path,runner=runner)
            turn=app.routes[('POST','/api/practice/generate')]({'concept_id':'a'})['turn'];app.wait(turn['id'],5)
            state=app.routes[('GET','/api/practice')]('')
            self.assertEqual(len(state['tasks']),1)
            self.assertEqual(state['tasks'][0]['source_refs'],[ref])
            self.assertNotIn('E=hf',state['tasks'][0]['question'])
            self.assertIn('Answer: E=hf',runner.prompt)
            app.close()
