import tempfile
import unittest
from guided_learning.api import execute

class Branches(unittest.TestCase):
    def test_question_survives_reopen_without_moving_mainline(self):
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op':'course.init','title':'Quantum'})
            execute(tmp, {'op':'curriculum.save','concepts':[{'id':'state','title':'State'}],'route':['state'],'coverage':[]})
            execute(tmp, {'op':'mainline.enter','concept_id':'state','goal':'probability','next_step':'projection','request_id':'p'})
            result=execute(tmp, {'op':'branch.begin','id':'q','question':'Why squared?','selection':'|a|²','anchor':{'scroll_y':320}})
            self.assertEqual(result['branch']['restore_point']['goal'],'probability')
            self.assertEqual(execute(tmp,{'op':'branch.list'})['branches'][0]['status'],'unanswered')
            self.assertEqual(execute(tmp,{'op':'course.status'})['position']['next_step'],'projection')

    def test_teacher_suggestion_waits_for_consent_and_return_keeps_anchor(self):
        import threading
        from guided_learning.web import LearningApp
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                if 'Branch decision protocol' not in prompt:
                    cancel.wait(3)
                    return
                text='Probability is the squared magnitude of the amplitude.\n<teaching-decision>{"depth":"long","category":"prerequisite","rationale":"Projection depends on distinguishing amplitudes from probabilities","suggest_supplement":true,"supplement_goal":"Amplitudes and probabilities"}</teaching-decision>'
                emit({'kind':'final','text':text}); emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op':'course.init','title':'Quantum'})
            execute(tmp, {'op':'curriculum.save','concepts':[{'id':'state','title':'State'}],'route':['state'],'coverage':[]})
            execute(tmp, {'op':'mainline.enter','concept_id':'state','goal':'probability','next_step':'projection','request_id':'p'})
            app=LearningApp(tmp,runner=Runner())
            try:
                app.start_turn({'id':'main','concept_id':'state','prompt':'Lecture'})
                app.routes[('POST','/api/branches/ask')]({'id':'q','question':'Why?','selection':'|a|²','main_turn_id':'main','anchor':{'scroll_y':320}})
                app.wait('branch:q',3)
                branch=app.operation({'op':'branch.read','id':'q'})['branch']
                self.assertEqual(branch['status'],'suggested')
                self.assertEqual(app.operation({'op':'stream.read','id':'main'})['turn']['status'],'running')
                app.routes[('POST','/api/branches/choose')]({'id':'q','choice':'accept'})
                self.assertEqual(app.operation({'op':'stream.read','id':'main'})['turn']['status'],'paused')
                returned=app.routes[('POST','/api/branches/return')]({'id':'q'})
                self.assertEqual(returned['branch']['anchor']['scroll_y'],320)
                self.assertEqual(app.snapshot()['position']['next_step'],'projection')
            finally: app.close()

    def test_invalid_decision_and_late_reply_do_not_resolve_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op':'course.init','title':'Quantum'})
            execute(tmp, {'op':'curriculum.save','concepts':[{'id':'state','title':'State'}],'route':['state'],'coverage':[]})
            execute(tmp, {'op':'mainline.enter','concept_id':'state','goal':'probability','next_step':'projection','request_id':'p'})
            execute(tmp, {'op':'branch.begin','id':'q','question':'Why?'})
            execute(tmp, {'op':'stream.start','id':'branch:q','concept_id':'state','prompt':'Why?','channel':'sidequestion'})
            execute(tmp, {'op':'stream.pause','id':'branch:q'})
            result=execute(tmp, {'op':'stream.event','id':'branch:q','attempt':1,'sequence':1,'kind':'final','text':'late'})
            self.assertTrue(result['ignored'])
            with self.assertRaises(ValueError):execute(tmp, {'op':'branch.decide','id':'q','decision':{'depth':'short'}})
            self.assertEqual(execute(tmp, {'op':'branch.read','id':'q'})['branch']['status'],'unanswered')

    def test_declining_supplement_is_idempotent_and_does_not_pause_main(self):
        from guided_learning.web import LearningApp
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                if 'Branch decision protocol' not in prompt:cancel.wait(3);return
                emit({'kind':'final','text':'First explain the distinction.<teaching-decision>{"depth":"short","category":"prerequisite","rationale":"Required for the current goal","suggest_supplement":true,"supplement_goal":"Foundations"}</teaching-decision>'})
                emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op':'course.init','title':'Quantum'})
            execute(tmp, {'op':'curriculum.save','concepts':[{'id':'state','title':'State'}],'route':['state'],'coverage':[]})
            execute(tmp, {'op':'mainline.enter','concept_id':'state','goal':'probability','next_step':'projection','request_id':'p'})
            app=LearningApp(tmp,runner=Runner())
            try:
                app.start_turn({'id':'main','concept_id':'state','prompt':'Lecture'})
                app.routes[('POST','/api/branches/ask')]({'id':'q','question':'Why?','main_turn_id':'main'})
                app.wait('branch:q',3)
                for _ in range(2):app.routes[('POST','/api/branches/choose')]({'id':'q','choice':'decline'})
                self.assertEqual(app.operation({'op':'stream.read','id':'main'})['turn']['status'],'running')
                self.assertEqual(app.operation({'op':'branch.read','id':'q'})['branch']['choice'],'decline')
            finally:app.close()

    def test_future_short_answer_remains_due_at_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Q'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'},{'id':'b','title':'B'}],'route':['a','b'],'coverage':[]})
            execute(tmp,{'op':'mainline.enter','concept_id':'a','goal':'A','next_step':'B','request_id':'p'})
            execute(tmp,{'op':'branch.begin','id':'q','question':'Why phase?'})
            execute(tmp,{'op':'stream.start','id':'branch:q','concept_id':'a','prompt':'Why phase?','channel':'sidequestion'})
            execute(tmp,{'op':'stream.event','id':'branch:q','attempt':1,'sequence':1,'kind':'final','text':'Later interference explains it.'})
            execute(tmp,{'op':'stream.event','id':'branch:q','attempt':1,'sequence':2,'kind':'complete'})
            execute(tmp,{'op':'branch.decide','id':'q','decision':{'depth':'short','category':'future','rationale':'interference later','suggest_supplement':False,'target_concept_id':'b'}})
            execute(tmp,{'op':'mainline.enter','concept_id':'b','goal':'B','next_step':'practice','request_id':'p2'})
            self.assertEqual(execute(tmp,{'op':'session.resume'})['due_explanations'][0]['target_concept_id'],'b')

    def test_host_supplement_prompt_is_not_learner_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Q'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
            execute(tmp,{'op':'stream.start','id':'auto','concept_id':'a','prompt':'Host explanation instructions','channel':'sidequestion','record_user':False})
            self.assertEqual(execute(tmp,{'op':'session.resume'})['recent_interactions'],[])

    def test_return_does_not_overwrite_newer_course_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Q'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'},{'id':'b','title':'B'}],'route':['a','b'],'coverage':[]})
            execute(tmp,{'op':'mainline.enter','concept_id':'a','goal':'A','next_step':'B','request_id':'p'})
            execute(tmp,{'op':'branch.begin','id':'q','question':'Why?','anchor':{'scroll_y':320}})
            execute(tmp,{'op':'mainline.enter','concept_id':'b','goal':'B','next_step':'practice','request_id':'p2'})
            returned=execute(tmp,{'op':'branch.return','id':'q'})
            self.assertEqual(returned['position']['concept_id'],'b')
            self.assertEqual(returned['branch']['restore_point']['concept_id'],'a')
            self.assertEqual(returned['branch']['status'],'unanswered')

    def test_older_selected_lecture_freezes_context_and_attribution_separate_from_recovery(self):
        from pathlib import Path
        from guided_learning.web import LearningApp
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                emit({'kind':'final','text':'A saved explanation'});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Q'})
            refs=[]
            for name in ('old','new'):
                p=Path(tmp)/(name+'.md');p.write_text(name+' source text',encoding='utf-8')
                source=execute(tmp,{'op':'source.register','path':str(p)})['source']
                refs.append({'source_id':source['id'],'revision':source['revision'],'unit_id':'line-1'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'a','title':'Old','links':[refs[0]]},{'id':'b','title':'New','links':[refs[1]]}],'route':['a','b'],'coverage':[]})
            app=LearningApp(tmp,runner=Runner())
            try:
                for concept in ('a','b'):
                    execute(tmp,{'op':'mainline.enter','concept_id':concept,'goal':concept,'next_step':'practice','request_id':concept})
                    app.start_turn({'id':concept,'concept_id':concept,'prompt':'Explain '+concept});app.wait(concept,3)
                ask=app.routes[('POST','/api/branches/ask')]
                branch=ask({'id':'q','question':'Old passage?','selection':'saved','selected_turn_id':'a','main_turn_id':'b'})['branch']
                app.wait('branch:q',3)
                self.assertEqual(branch['selected_turn_id'],'a')
                self.assertEqual(branch['selected_lecture']['prompt_snapshot']['context']['concept']['id'],'a')
                self.assertEqual(branch['restore_point']['concept_id'],'b')
                turn=app.operation({'op':'stream.read','id':'branch:q'})['turn']
                self.assertIn('old source text',app.build_prompt(turn))
                self.assertCountEqual(turn['source_refs'],refs)
                answer=next(x for x in app.snapshot()['session']['recent_interactions'] if x['id']=='stream:branch:q')
                self.assertCountEqual(answer['source_refs'],refs)
                with self.assertRaises(ValueError):ask({'id':'bad','question':'?','selected_turn_id':'branch:q','main_turn_id':'b'})
                with self.assertRaises(ValueError):ask({'id':'stale','question':'?','main_turn_id':'a'})
                with self.assertRaises(ValueError):ask({'id':'q','question':'Old passage?','selection':'saved','selected_turn_id':'b','main_turn_id':'b'})
                execute(tmp,{'op':'mainline.enter','concept_id':'a','goal':'later','next_step':'practice','request_id':'later'})
                app.routes[('POST','/api/branches/return')]({'id':'q'})
                self.assertEqual(app.snapshot()['position']['goal'],'later')
                self.assertEqual(app.operation({'op':'branch.read','id':'q'})['branch']['selected_lecture'],branch['selected_lecture'])
            finally:app.close()

    def test_interrupted_supplement_reopens_and_completes_once(self):
        from guided_learning.web import LearningApp
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                emit({'kind':'final','text':'Recovered complete supplement'});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp,{'op':'course.init','title':'Q'})
            execute(tmp,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
            execute(tmp,{'op':'mainline.enter','concept_id':'a','goal':'Original goal','next_step':'practice','request_id':'p'})
            execute(tmp,{'op':'branch.begin','id':'q','question':'Need foundation'})
            execute(tmp,{'op':'stream.start','id':'branch:q','concept_id':'a','prompt':'Need foundation','channel':'sidequestion'})
            execute(tmp,{'op':'stream.event','id':'branch:q','attempt':1,'sequence':1,'kind':'final','text':'Accept supplement?'})
            execute(tmp,{'op':'stream.event','id':'branch:q','attempt':1,'sequence':2,'kind':'complete'})
            execute(tmp,{'op':'branch.decide','id':'q','decision':{'depth':'short','category':'prerequisite','rationale':'Foundation needed','suggest_supplement':True,'supplement_goal':'Foundation'}})
            execute(tmp,{'op':'branch.choose','id':'q','choice':'accept'})
            execute(tmp,{'op':'stream.start','id':'supplement:q','concept_id':'a','prompt':'Explain foundation','channel':'sidequestion','record_user':False})
            execute(tmp,{'op':'stream.event','id':'supplement:q','attempt':1,'sequence':1,'kind':'delta','text':'Partial explanation'})
            app=LearningApp(tmp,runner=Runner())
            try:
                self.assertEqual(app.operation({'op':'stream.read','id':'supplement:q'})['turn']['status'],'interrupted')
                app.resume_turn('supplement:q','retry');app.wait('supplement:q',3)
                app.resume_turn('supplement:q','retry')
                result=app.operation({'op':'stream.read','id':'supplement:q'})['turn']
                self.assertEqual(result['status'],'completed');self.assertEqual(result['attempt'],2)
                self.assertEqual(result['attempts'][0]['text'],'Partial explanation')
                self.assertEqual(len(app.operation({'op':'branch.list'})['branches']),1)
                saved=[i for i in app.snapshot()['session']['recent_interactions'] if i['id']=='stream:supplement:q']
                self.assertEqual(len(saved),1);self.assertEqual(saved[0]['text'],'Recovered complete supplement')
                self.assertEqual(app.snapshot()['position']['goal'],'Original goal')
            finally:app.close()
