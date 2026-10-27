import json
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
            self.assertIn('starts with its label',prompt)
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
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'Photons','exercises':[{**ref,'question':'1(a)','required_concepts':['a']}]}],'route':['a'],'coverage':[]})
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


class AskFlow(unittest.TestCase):
    def test_asking_about_a_solved_exercise_records_no_assessment(self):
        from guided_learning.store import OperationError
        class Runner:
            reply='';prompts=[]
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt);emit({'kind':'final','text':self.reply});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
            runner=Runner();app=Host(path,runner=runner)
            def run(start,text):
                runner.reply=text;t=app.wait(start()['turn']['id'],5);self.assertEqual(t['status'],'completed',t)
                return app.practice.state()
            tid=run(lambda:app.practice.generate('a'),'{"questions":[{"question":"1. State it.\\n2. Apply it.","origin":"self_created","source_refs":[]}]}')['tasks'][0]['id']
            run(lambda:app.practice.act(tid,'assess','Both parts.'),'{"feedback":"Correct.","parts":["correct","correct"]}')
            evidence=execute(path,{'op':'evidence.view','concept_id':'a'})['history']
            state=run(lambda:app.practice.act(tid,'ask',question='What does part 2 mean by apply?'),'{"feedback":"Use the rule on a new case."}')
            self.assertIn('What does part 2 mean by apply?',runner.prompts[-1])
            self.assertIn('never assessed',runner.prompts[-1])
            task=state['tasks'][0]
            self.assertEqual(task['status'],'attempted')
            self.assertEqual(task['history'][-1],{'action':'ask','question':'What does part 2 mean by apply?','feedback':'Use the rule on a new case.'})
            self.assertEqual([h['outcome'] for h in task['history'] if h['action']=='assess'],['passed'])
            self.assertEqual(execute(path,{'op':'evidence.view','concept_id':'a'})['history'],evidence)
            self.assertIn('What does part 2 mean by apply?',[i['text'] for i in app.snapshot()['session']['recent_interactions']])
            # A reply that gives an outcome anyway is still only an answer.
            state=run(lambda:app.practice.act(tid,'ask',question='Is my answer right?'),'{"feedback":"Use Check my answer for that.","outcome":"needs_work"}')
            self.assertEqual(set(state['tasks'][0]['history'][-1]),{'action','question','feedback'})
            self.assertEqual(execute(path,{'op':'evidence.view','concept_id':'a'})['history'],evidence)
            with self.assertRaises(OperationError) as caught: app.practice.act(tid,'ask',question='  ')
            self.assertEqual(caught.exception.code,'empty_question')
            app.close()

    def test_an_ask_job_needs_a_question(self):
        from guided_learning.store import OperationError
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
            with self.assertRaises(OperationError) as caught:
                execute(path,{'op':'practice.job','job':{'id':'j','concept_id':'a','action':'ask','task_id':'t'}})
            self.assertEqual(caught.exception.code,'invalid_request')


class PartsFlow(unittest.TestCase):
    """Exercises are assessed part by part (ADR 0011)."""
    def setUp(self):
        class Runner:
            reply='';prompts=[]
            def run(self,prompt,cwd,emit,cancel):
                self.prompts.append(prompt);emit({'kind':'final','text':self.reply});emit({'kind':'complete'})
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);path=self.path=self.tmp.name
        execute(path,{'op':'course.init','title':'Physics'})
        execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'A'}],'route':['a'],'coverage':[]})
        self.runner=Runner();self.app=Host(path,runner=self.runner);self.addCleanup(self.app.close)

    def run_job(self,start,text):
        self.runner.reply=text;t=self.app.wait(start()['turn']['id'],5);self.assertEqual(t['status'],'completed',t)
        return self.app.practice.state()

    def generate(self,parts):
        question={'question':'Setup.\n1. State it.\n2. Apply it.\n3. Check it.','origin':'self_created','source_refs':[],'parts':parts}
        return self.run_job(lambda:self.app.practice.generate('a'),json.dumps({'questions':[question]}))['tasks'][0]

    def assess(self,tid,answer,parts,feedback='Checked.'):
        return self.run_job(lambda:self.app.practice.act(tid,'assess',answer),json.dumps({'feedback':feedback,'parts':parts}))

    def test_a_multi_part_exercise_answered_part_by_part(self):
        task=self.generate(['State it.','Apply it.','Check it.'])
        self.assertEqual(task['parts'],['State it.','Apply it.','Check it.'])
        self.assertIn('"parts"',next(p for p in self.runner.prompts if 'Practice only' in p))
        state=self.assess(task['id'],'Part 1: the rule.',['correct','not_attempted','not_attempted'])
        prompt=self.runner.prompts[-1]
        self.assertIn('partly_correct',prompt);self.assertIn('not_attempted',prompt)
        last=state['tasks'][0]['history'][-1]
        self.assertEqual((last['parts'],last['outcome'],last['kind']),(['correct','not_attempted','not_attempted'],'needs_work','needs_work'))
        self.assertEqual(execute(self.path,{'op':'evidence.view','concept_id':'a'})['latest_assessment']['parts'],['correct','not_attempted','not_attempted'])
        state=self.assess(task['id'],'Part 2 and 3.',['not_attempted','correct','partly_correct'])
        self.assertIn('"parts": ["correct", "not_attempted", "not_attempted"]',self.runner.prompts[-1],'the teacher sees the statuses so far')
        last=state['tasks'][0]['history'][-1]
        self.assertEqual((last['parts'],last['outcome']),(['correct','correct','partly_correct'],'needs_work'),'only the addressed parts change')
        state=self.assess(task['id'],'Part 3 fixed.',['not_attempted','not_attempted','correct'])
        last=state['tasks'][0]['history'][-1]
        self.assertEqual((last['parts'],last['outcome'],last['kind']),(['correct']*3,'passed','hinted'),'feedback correcting part 3 was help')
        self.assertFalse(execute(self.path,{'op':'evidence.view','concept_id':'a'})['independently_verified'])

    def test_parts_may_carry_short_labels(self):
        for parts in ([{'label':'(a)'}],[{'label':5,'text':'State it.'}],[{'label':'x'*41,'text':'State it.'}],[{'text':'State it.','extra':1}]):
            with self.subTest(parts=parts):
                state=self.run_job(lambda:self.app.practice.generate('a'),json.dumps({'questions':[{'question':'Q.','origin':'self_created','source_refs':[],'parts':parts}]}))
                self.assertIn('error',[j for j in state['jobs'] if j['action']=='generate'][-1])
        labelled=[{'label':'(a)','text':'State it.'},'Apply it.',{'text':'Check it.'}]
        self.assertEqual(self.generate(labelled)['parts'],labelled)
        self.assertIn('"label"',next(p for p in self.runner.prompts if 'Practice only' in p))

    def test_correct_parts_one_at_a_time_stay_independent(self):
        task=self.generate(['State it.','Apply it.','Check it.'])
        self.assess(task['id'],'Part 1.',['correct','not_attempted','not_attempted'])
        self.assertIn('Give no hint or cue for a part the answer does not address',self.runner.prompts[-1])
        state=self.assess(task['id'],'Parts 2 and 3.',['not_attempted','correct','correct'])
        last=state['tasks'][0]['history'][-1]
        self.assertEqual((last['outcome'],last['kind']),('passed','independent'))
        self.assertTrue(execute(self.path,{'op':'evidence.view','concept_id':'a'})['independently_verified'])

    def test_an_exercise_from_before_parts_is_assessed_by_its_numbered_subquestions(self):
        task=self.run_job(lambda:self.app.practice.generate('a'),json.dumps({'questions':[{'question':'Setup.\n（1）State it.\n（2）Apply it.\n（3）Check it.','origin':'self_created','source_refs':[]}]}))['tasks'][0]
        self.assertNotIn('parts',task,'generated as an old exercise would have been')
        from guided_learning.store import Store
        store=Store(self.path)  # saved before parts: no parts, and an earlier answer assessed as a whole
        with store.db:
            saved=store.get('practice_tasks',task['id'])
            saved['history']=[{'action':'assess','feedback':'Part 1 right; 2 and 3 open.','outcome':'needs_work','kind':'needs_work','answer':'Part 1.'}]
            store.put('practice_tasks',task['id'],saved)
        store.db.close()
        state=self.assess(task['id'],'Part 2.',['correct','correct','not_attempted'])
        task=state['tasks'][0]
        self.assertEqual([p['label'] for p in task['parts']],['（1）','（2）','（3）'])
        self.assertEqual(task['history'][-1]['parts'],['correct','correct','not_attempted'])
        prompt=self.runner.prompts[-1]
        self.assertIn('exactly 3 part statuses',prompt)
        self.assertIn('earlier ones included',prompt,'parts answered before the exercise had parts can still count')

    def test_part_statuses_must_match_the_parts(self):
        task=self.generate(['State it.','Apply it.','Check it.'])
        state=self.assess(task['id'],'All.',['correct','correct'])
        assessed=lambda state:[j for j in state['jobs'] if j['action']=='assess']
        self.assertTrue(all('error' in j for j in assessed(state)))
        state=self.run_job(lambda:self.app.practice.act(task['id'],'assess','All.'),json.dumps({'feedback':'Good.','outcome':'passed'}))
        self.assertEqual(len(assessed(state)),2)
        self.assertTrue(all('error' in j for j in assessed(state)),'a multi-part exercise needs part statuses')
        self.assertEqual(state['tasks'][0]['history'],[])

    def test_a_task_without_parts_is_one_part(self):
        tid=self.run_job(lambda:self.app.practice.generate('a'),'{"questions":[{"question":"2+2?","origin":"self_created","source_refs":[]}]}')['tasks'][0]['id']
        state=self.run_job(lambda:self.app.practice.act(tid,'assess','5'),json.dumps({'feedback':'No.','parts':['not_yet']}))
        self.assertEqual(state['tasks'][0]['history'][-1]['parts'],['not_yet'])
        state=self.run_job(lambda:self.app.practice.act(tid,'assess','4'),json.dumps({'feedback':'Yes.','outcome':'passed'}))
        last=state['tasks'][0]['history'][-1]
        self.assertEqual((last['parts'],last['outcome']),(['correct'],'passed'),'an outcome alone still assesses a single part')

    def test_an_assessment_from_before_parts_counts_as_its_one_part(self):
        from guided_learning import practice
        old=lambda outcome:{'history':[{'action':'assess','outcome':outcome,'kind':'independent'},{'action':'hint','feedback':'.'}]}
        self.assertEqual((practice.part_statuses(old('passed')),practice.part_statuses(old('needs_work'))),(['correct'],['not_yet']))
        self.assertEqual(practice.part_statuses({'parts':['x','y'],'history':[]}),['not_attempted']*2)


class ExerciseOrigin(unittest.TestCase):
    """A generated task names the course exercise it uses, so a homework part shows its question (ADR 0012)."""
    def generate(self, exercises, question):
        from pathlib import Path
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                self.prompt=prompt
                emit({'kind':'final','text':json.dumps({'questions':[question(ref)]})});emit({'kind':'complete'})
        with tempfile.TemporaryDirectory() as path:
            execute(path,{'op':'course.init','title':'Physics'})
            file=Path(path)/'homework.md';file.write_text('7. (a) Normalize. (b) Measure.',encoding='utf-8')
            source=execute(path,{'op':'source.register','path':str(file)})['source']
            ref={'source_id':source['id'],'revision':source['revision'],'unit_id':'line-1'}
            execute(path,{'op':'curriculum.save','concepts':[{'id':'a','title':'States','exercises':[{**ref,'required_concepts':['a'],**e} for e in exercises]}],'route':['a'],'coverage':[]})
            runner=Runner();app=Host(path,runner=runner)
            app.wait(app.practice.generate('a')['turn']['id'],5)
            state=app.practice.state()
            app.close()
            return state,runner.prompt

    def test_the_task_keeps_the_exercise_the_teacher_names(self):
        part={'question':'7(a)','part_of':'7','other_parts':[{'question':'7(b)'}]}
        state,prompt=self.generate([part,{'question':'8'}],lambda ref:{'question':'Normalize.','origin':'source','source_refs':[ref],'exercise':'7(a)'})
        self.assertEqual(state['tasks'][0]['exercise'],'7(a)')
        self.assertIn('"exercise"',prompt)

    def test_a_task_from_the_only_exercise_of_its_source_unit_takes_that_exercise(self):
        state,_=self.generate([{'question':'7(a)','part_of':'7'}],lambda ref:{'question':'Normalize.','origin':'source','source_refs':[ref]})
        self.assertEqual(state['tasks'][0]['exercise'],'7(a)')

    def test_an_ambiguous_or_self_created_task_names_no_exercise(self):
        state,_=self.generate([{'question':'7(a)'},{'question':'8'}],lambda ref:{'question':'Normalize.','origin':'source','source_refs':[ref]})
        self.assertNotIn('exercise',state['tasks'][0])
        state,_=self.generate([{'question':'7(a)'}],lambda ref:{'question':'Invent.','origin':'self_created','source_refs':[]})
        self.assertNotIn('exercise',state['tasks'][0])

    def test_naming_an_exercise_the_section_does_not_have_is_rejected(self):
        state,_=self.generate([{'question':'7(a)'}],lambda ref:{'question':'Normalize.','origin':'source','source_refs':[ref],'exercise':'9'})
        self.assertEqual(state['tasks'],[])
        self.assertIn('exercise',state['jobs'][0]['error'])
