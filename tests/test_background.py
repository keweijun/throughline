from support import call_cli
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class BackgroundCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / 'course'
        self.settings = Path(self.temp.name) / 'settings.json'
        environment = patch.dict(os.environ, {'GUIDED_LEARNING_CONFIG': str(self.settings)})
        environment.start()
        self.addCleanup(environment.stop)
        self.call('course.init', title='Quantum')
        self.call('curriculum.save', concepts=[{'id':'state','title':'State'}], route=['state'], coverage=[])
        self.call('mainline.enter', concept_id='state', goal='States', next_step='Normalize')
        self.call('interaction.record', id='u1', role='user', text='A wavefunction represents a state.', concept_id='state')

    def call(self, op, error=None, workspace=None, **fields):
        return call_cli(self, workspace or self.workspace, op, error=error, **fields)

    def test_handoff_names_the_learners_small_model(self):
        self.settings.write_text(json.dumps({'model': 'gpt-6.1-sol', 'small_model': 'gpt-5.6-luna'}), encoding='utf-8')
        self.call('background.enqueue', id='job', interaction_ids=['u1'], concept_id='state')
        claim = self.call('background.claim', id='job', request_id='claim', attempt_id='attempt-1')
        self.assertEqual(claim['handoff']['model'], 'gpt-5.6-luna')

    def test_queue_survives_unavailable_host_and_retries_without_duplicate_claims(self):
        first = self.call('background.enqueue', id='job', interaction_ids=['u1'], concept_id='state')
        self.assertEqual(first, self.call('background.enqueue', id='job', interaction_ids=['u1'], concept_id='state'))
        self.call('background.pause', id='job', request_id='pause', reason='Host Luna unavailable')
        self.assertEqual(self.call('background.view', id='job')['job']['status'], 'paused')
        self.call('background.retry', id='job', request_id='retry')
        claim = self.call('background.claim', id='job', request_id='claim', attempt_id='attempt-1')
        self.assertEqual(claim, self.call('background.claim', id='job', request_id='claim', attempt_id='attempt-1'))
        self.assertEqual(claim['handoff']['model'], 'gpt-6-luna')
        self.assertEqual(claim['handoff']['interactions'][0]['text'], 'A wavefunction represents a state.')
        self.assertFalse(claim['model_call_performed'])
        self.assertEqual(self.call('session.resume')['position']['next_step'], 'Normalize')
    def test_teacher_accepts_only_derived_notes_with_original_provenance(self):
        self.call('background.enqueue', id='job', interaction_ids=['u1'], concept_id='state')
        self.call('background.claim', id='job', request_id='claim', attempt_id='one')
        notes = [{'text':'Learner describes the wavefunction as a state representation.', 'interaction_ids':['u1']}]
        self.call('background.submit', id='job', request_id='submit', attempt_id='one', notes=notes)
        self.assertEqual(self.call('background.view', id='job')['job']['status'], 'candidate')
        accepted = self.call('background.review', id='job', request_id='accept', decision='accept', reason='Matches the actual learner statement')
        self.assertEqual(accepted['job']['status'], 'accepted')
        self.assertEqual(accepted, self.call('background.review', id='job', request_id='accept', decision='accept', reason='Matches the actual learner statement'))
        self.assertEqual(len(self.call('background.view')['notes']), 1)
        self.assertEqual(self.call('evidence.view', concept_id='state')['status'], 'unverified')
        self.assertEqual(self.call('session.resume')['recent_interactions'][0]['text'], 'A wavefunction represents a state.')
    def test_new_interaction_and_assessment_make_old_results_stale(self):
        self.call('background.enqueue', id='job', interaction_ids=['u1'], concept_id='state')
        self.call('background.claim', id='job', request_id='claim1', attempt_id='one')
        self.call('interaction.record', id='a1', role='assistant', text='That is correct.', concept_id='state')
        stale = self.call('background.submit', id='job', request_id='submit1', attempt_id='one', notes=[{'text':'A note', 'interaction_ids':['u1']}])
        self.assertEqual(stale['job']['status'], 'stale')
        self.assertEqual(self.call('background.view')['notes'], [])
        self.call('background.retry', id='job', request_id='retry')
        self.call('background.claim', id='job', request_id='claim2', attempt_id='two')
        self.call('background.submit', id='job', request_id='submit2', attempt_id='two', notes=[{'text':'A note', 'interaction_ids':['u1']}])
        self.call('evidence.assess', id='assessment', concept_id='state', session_id='s', exercise_id='e', answer_id='u1', assessment_id='a1', outcome='passed')
        stale_review = self.call('background.review', id='job', request_id='review', decision='accept', reason='Reviewed')
        self.assertEqual(stale_review['job']['status'], 'stale')
        self.assertEqual(self.call('background.view')['notes'], [])
        self.assertEqual(self.call('evidence.view', concept_id='state')['status'], 'independent')
    def test_candidate_cannot_cite_unprovided_messages_sources_or_patch_state(self):
        self.call('interaction.record', id='other', role='assistant', text='Outside the handoff')
        self.call('background.enqueue', id='job', interaction_ids=['u1'], concept_id='state')
        self.call('background.claim', id='job', request_id='claim', attempt_id='one')
        self.call('background.submit', error='invalid_reference', id='job', request_id='bad-msg', attempt_id='one', notes=[{'text':'Invented scope', 'interaction_ids':['other']}])
        self.call('background.submit', error='invalid_reference', id='job', request_id='bad-source', attempt_id='one', notes=[{'text':'Invented source', 'interaction_ids':['u1'], 'source_refs':[{'source_id':'absent','revision':'no','unit_id':'page-1'}]}])
        self.call('background.submit', error='invalid_request', id='job', request_id='bad-patch', attempt_id='one', notes=[{'text':'Upgrade learner', 'interaction_ids':['u1'], 'mastery':'independent'}])
        self.assertEqual(self.call('background.view', id='job')['job']['status'], 'running')
    def test_old_attempt_cannot_submit_and_accepted_notes_are_marked_stale_after_progress(self):
        self.call('background.enqueue', id='job', interaction_ids=['u1'], concept_id='state')
        self.call('background.claim', id='job', request_id='claim1', attempt_id='one')
        self.call('background.pause', id='job', request_id='pause', reason='Session ended')
        self.call('background.retry', id='job', request_id='retry')
        self.call('background.claim', id='job', request_id='claim2', attempt_id='two')
        self.call('background.submit', error='invalid_transition', id='job', request_id='old-submit', attempt_id='one', notes=[{'text':'Old', 'interaction_ids':['u1']}])
        self.call('background.submit', id='job', request_id='submit', attempt_id='two', notes=[{'text':'Current', 'interaction_ids':['u1']}])
        self.call('background.review', id='job', request_id='accept', decision='accept', reason='Verified')
        self.assertFalse(self.call('background.view')['notes'][0]['stale'])
        self.call('mainline.enter', concept_id='state', goal='States', next_step='Compute normalization')
        self.assertTrue(self.call('background.view')['notes'][0]['stale'])
        self.call('background.pause', error='id_conflict', id='job', request_id='pause', reason='Different reason')
