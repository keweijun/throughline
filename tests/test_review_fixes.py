import tempfile
import unittest
from pathlib import Path
from support import call_cli

class ReviewFixes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.workspace=self.base/'course'
        self.call('course.init',title='Course')
        self.call('curriculum.save',concepts=[{'id':'a','title':'A'},{'id':'b','title':'B'},{'id':'c','title':'C'}],route=['a','b','c'])

    def call(self,op,error=None,**fields):
        return call_cli(self,self.workspace,op,error=error,**fields)

    def test_old_checkpoint_and_mainline_retries_preserve_current_position(self):
        for op in ('mainline.enter','position.save'):
            a={'concept_id':'a','goal':'A','next_step':'First'}
            b={'concept_id':'b','goal':'B','next_step':'Second'}
            fields_a={'position':a} if op=='position.save' else a
            fields_b={'position':b} if op=='position.save' else b
            self.call(op,request_id=op+'-1',**fields_a)
            self.call(op,request_id=op+'-2',**fields_b)
            retried=self.call(op,request_id=op+'-1',**fields_a)
            self.assertEqual(self.call('session.resume')['position']['concept_id'],'b')
            self.assertTrue(retried['replayed'])
            self.assertEqual(retried['position']['concept_id'],'b')
            self.call(op,error='id_conflict',request_id=op+'-1',**fields_b)
            self.call(op,error='invalid_request',request_id=None,**fields_a)
    def test_historical_evidence_keeps_original_source_revision_after_relink(self):
        path=self.base/'lesson.md'
        path.write_text('Original definition',encoding='utf-8')
        source=self.call('source.register',path=str(path))['source']
        ref={'source_id':source['id'],'revision':source['revision'],'unit_id':'line-1'}
        model={'concepts':[{'id':'a','title':'A','links':[ref]},{'id':'b','title':'B'},{'id':'c','title':'C'}],'route':['a','b','c']}
        self.call('curriculum.save',**model)
        answer={'id':'answer','role':'user','text':'My answer','concept_id':'a'}
        original=self.call('interaction.record',**answer)['interaction']
        self.call('interaction.record',id='assessment',role='assistant',text='Correct',concept_id='a')
        assessment={'id':'pass','concept_id':'a','session_id':'s','exercise_id':'q','answer_id':'answer','assessment_id':'assessment','outcome':'passed'}
        self.call('evidence.assess',**assessment)
        path.write_text('Changed definition',encoding='utf-8')
        newer=self.call('source.register',path=str(path))['source']
        model['concepts'][0]['links'][0]={**ref,'revision':newer['revision']}
        self.call('curriculum.save',**model)
        history=self.call('evidence.view',concept_id='a')['history'][0]
        self.assertEqual(history['answer_source_refs'],[ref])
        self.assertEqual(history['assessment_source_refs'],[ref])
        self.assertEqual(original['source_refs'],[ref])
        self.assertEqual(self.call('interaction.record',**answer)['interaction'],original)
        self.assertEqual(self.call('evidence.assess',**assessment)['evidence'],history)
        self.call('interaction.record',error='invalid_reference',id='bad',role='user',text='Bad ref',concept_id='a',source_refs=[{**ref,'unit_id':'page-999'}])
    def test_deferred_confirmation_accepts_target_context_but_rejects_unrelated_context(self):
        self.call('evidence.defer',id='defer-a',concept_id='a',target_concept_id='b',reason='Review at B')
        self.call('mainline.enter',concept_id='b',goal='B',next_step='Review A')
        self.call('interaction.record',id='confirm-b',role='user',text='That answers the earlier A question.',concept_id='b')
        self.call('interaction.record',id='unrelated',role='user',text='I understood C.',concept_id='c')
        self.call('evidence.resolve',error='invalid_evidence',id='bad-resolve',deferred_id='defer-a',interaction_id='unrelated')
        resolution=self.call('evidence.resolve',id='resolve-a',deferred_id='defer-a',interaction_id='confirm-b')
        self.assertEqual(resolution['resolution']['interaction_id'],'confirm-b')
        self.assertEqual(self.call('evidence.review',concept_id='b')['due'],[])
        self.assertEqual(self.call('evidence.view',concept_id='a')['status'],'unverified')
    def test_historical_answer_and_assessment_are_readable_after_recent_window_expires(self):
        self.call('interaction.record',id='answer',role='user',text='Original answer',concept_id='a')
        self.call('interaction.record',id='assessment',role='assistant',text='Original feedback',concept_id='a')
        self.call('evidence.assess',id='pass',concept_id='a',session_id='s',exercise_id='q',answer_id='answer',assessment_id='assessment',outcome='passed')
        for n in range(21):
            self.call('interaction.record',id='later-'+str(n),role='user',text='Later message')
        recent=self.call('session.resume',recent_limit=20)['recent_interactions']
        self.assertNotIn('answer',[message['id'] for message in recent])
        evidence=self.call('evidence.view',concept_id='a')['history'][0]
        self.assertEqual(self.call('interaction.read',id=evidence['answer_id'])['interaction']['text'],'Original answer')
        self.assertEqual(self.call('interaction.read',id=evidence['assessment_id'])['interaction']['text'],'Original feedback')
        self.call('interaction.read',id='unknown',error='invalid_interaction')
    def test_explicit_source_reference_retry_keeps_its_original_payload(self):
        path=self.base/'source.md'
        path.write_text('Definition',encoding='utf-8')
        source=self.call('source.register',path=str(path))['source']
        ref={'source_id':source['id'],'revision':source['revision'],'unit_id':'line-1'}
        fields={'id':'explicit','role':'user','text':'Answer','concept_id':'a','source_refs':[ref,ref]}
        original=self.call('interaction.record',**fields)
        self.assertEqual(self.call('interaction.record',**fields),original)
