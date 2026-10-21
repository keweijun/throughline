import tempfile
import unittest
from guided_learning.api import execute

class StreamingCourse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = self.tmp.name
        self.call('course.init', title='Quantum')
        self.call('curriculum.save', concepts=[{'id':'state','title':'States'}], route=['state'], coverage=[])

    def call(self, op, **kwargs):
        return execute(self.workspace, {'op':op, **kwargs})

    def test_only_authoritative_completed_turn_becomes_one_interaction(self):
        turn = self.call('stream.start', id='lecture', concept_id='state', prompt='Explain states')['turn']
        self.call('stream.event', id='lecture', attempt=1, sequence=1, kind='delta', text='partial')
        self.assertEqual([i for i in self.call('session.resume')['recent_interactions'] if i['role']=='assistant'], [])
        self.call('stream.event', id='lecture', attempt=1, sequence=2, kind='final', text='Complete explanation.')
        self.assertEqual([i for i in self.call('session.resume')['recent_interactions'] if i['role']=='assistant'], [])
        event = dict(id='lecture', attempt=1, sequence=3, kind='complete')
        self.call('stream.event', **event)
        self.call('stream.event', **event)
        self.assertEqual(self.call('stream.read', id='lecture')['turn']['text'], 'Complete explanation.')
        history = self.call('session.resume')['recent_interactions']
        self.assertEqual([(i['id'], i['text']) for i in history], [('stream-user:lecture','Explain states'),('stream:lecture','Complete explanation.')])

    def test_pause_rejects_late_completion_and_resume_is_idempotent_across_reopen(self):
        self.call('stream.start', id='lecture', concept_id='state', prompt='Explain states')
        self.call('stream.event', id='lecture', attempt=1, sequence=1, kind='delta', text='unfinished')
        self.call('stream.pause', id='lecture')
        self.call('stream.event', id='lecture', attempt=1, sequence=2, kind='final', text='late')
        self.assertEqual(self.call('stream.read', id='lecture')['turn']['status'],'paused')
        self.assertEqual([i for i in self.call('session.resume')['recent_interactions'] if i['role']=='assistant'],[])
        resumed = self.call('stream.resume', id='lecture', request_id='resume1')['turn']
        self.assertEqual(resumed['attempt'],2)
        self.assertEqual(resumed['attempts'][0]['text'],'unfinished')
        self.call('stream.resume', id='lecture', request_id='resume1')
        self.call('stream.event', id='lecture', attempt=1, sequence=3, kind='complete')
        self.call('stream.event', id='lecture', attempt=2, sequence=1, kind='final', text='Recovered whole lesson.')
        self.call('stream.event', id='lecture', attempt=2, sequence=2, kind='complete')
        self.assertEqual(self.call('interaction.read',id='stream:lecture')['interaction']['text'],'Recovered whole lesson.')

    def test_host_restart_exposes_incomplete_stream_and_out_of_order_is_rejected(self):
        from guided_learning.store import OperationError
        self.call('stream.start', id='lecture', concept_id='state', prompt='Explain states')
        with self.assertRaises(OperationError):
            self.call('stream.event', id='lecture', attempt=1, sequence=2, kind='delta', text='gap')
        self.call('stream.recover')
        self.assertEqual(self.call('stream.read',id='lecture')['turn']['status'],'interrupted')
        self.assertEqual([i for i in self.call('session.resume')['recent_interactions'] if i['role']=='assistant'],[])

    def test_source_snapshot_stays_bound_to_prompt_and_record_after_revision_change(self):
        from pathlib import Path
        from guided_learning.server import Host
        path=Path(self.workspace)/'lesson.md'
        path.write_text('OLD_SOURCE_FACT',encoding='utf-8')
        old=self.call('source.register',path=str(path))['source']
        ref={'source_id':old['id'],'revision':old['revision'],'unit_id':'line-1'}
        self.call('curriculum.save',concepts=[{'id':'state','title':'States','links':[ref]}],route=['state'],coverage=[])
        turn=self.call('stream.start',id='lesson',concept_id='state',prompt='Teach this source')['turn']
        path.write_text('NEW_SOURCE_FACT',encoding='utf-8')
        new=self.call('source.register',path=str(path))['source']
        newref={**ref,'revision':new['revision']}
        self.call('curriculum.save',concepts=[{'id':'state','title':'States','links':[newref]}],route=['state'],coverage=[])
        app=Host(self.workspace)
        try:
            prompt=app.build_prompt(turn)
            self.assertIn('OLD_SOURCE_FACT',prompt)
            self.assertNotIn('NEW_SOURCE_FACT',prompt)
        finally: app.close()
        self.call('stream.resume',id='lesson',request_id='regenerate')
        self.call('stream.event',id='lesson',attempt=2,sequence=1,kind='final',text='Explanation of the old source.')
        self.call('stream.event',id='lesson',attempt=2,sequence=2,kind='complete')
        self.assertEqual(self.call('interaction.read',id='stream:lesson')['interaction']['source_refs'],[ref])
        self.assertEqual(self.call('stream.read',id='lesson')['turn']['attempts'][0]['source_refs'],[ref])
