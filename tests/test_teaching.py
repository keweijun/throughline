import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TeachingCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / 'course'
        self.call('course.init', title='Quantum')
        self.call('curriculum.save', concepts=[{'id':'state','title':'State'},{'id':'projection','title':'Projection','prerequisites':['state']}], route=['state','projection'], coverage=[])

    def call(self, op, error=None, **fields):
        process = subprocess.run([sys.executable, '-m', 'guided_learning', '--workspace', str(self.workspace)], input=json.dumps({'op':op, **fields}), text=True, encoding='utf-8', capture_output=True, cwd=ROOT)
        response = json.loads(process.stdout)
        if error:
            self.assertEqual(response['error']['code'], error, response)
            self.assertNotEqual(process.returncode, 0)
            return response
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return response['result']

    def test_raw_interaction_retries_are_immutable_and_resume_returns_bounded_history(self):
        first = self.call('interaction.record', id='u1', role='user', text='Why a function?', concept_id='state')['interaction']
        retry = self.call('interaction.record', id='u1', role='user', text='Why a function?', concept_id='state')['interaction']
        self.assertEqual(first, retry)
        self.call('interaction.record', error='id_conflict', id='u1', role='user', text='Changed', concept_id='state')
        self.call('interaction.record', id='a1', role='assistant', text='It is the position representation.', concept_id='state')
        session = self.call('session.resume', recent_limit=1)
        self.assertEqual(len(session['recent_interactions']), 1)
        self.assertEqual(session['recent_interactions'][0]['id'], 'a1')
        self.assertIsNone(session['position'])
    def test_short_sidequestion_restores_mainline_and_long_answer_waits_across_restart(self):
        position = self.call('mainline.enter', concept_id='state', goal='Understand states', next_step='Normalize psi')['position']
        self.call('interaction.record', id='q1', role='user', text='What is psi?', concept_id='state')
        self.call('sidequestion.open', id='s1', interaction_id='q1', category='local', depth='short', rationale='Only the symbol is missing', strategy='definition')
        self.call('interaction.record', id='a1', role='assistant', text='Psi represents the state in position coordinates.', concept_id='state')
        answered = self.call('sidequestion.answer', id='s1', answer_interaction_id='a1')
        self.assertEqual(answered['branch']['status'], 'resumed')
        self.assertEqual(self.call('session.resume')['position'], position)
        self.call('interaction.record', id='q2', role='user', text='Explain this in depth.', concept_id='state')
        branch = self.call('sidequestion.open', id='s2', interaction_id='q2', category='local', depth='short', explicit_deepen=True, rationale='Learner requests depth', strategy='worked_example')['branch']
        self.assertEqual(branch['depth'], 'long')
        self.call('interaction.record', id='a2', role='assistant', text='A complete conceptual explanation.', concept_id='state')
        self.call('sidequestion.answer', id='s2', answer_interaction_id='a2')
        resumed = self.call('session.resume')
        self.assertEqual(resumed['active_branch']['status'], 'waiting')
        self.assertEqual(resumed['active_branch']['restore_point'], position)
        self.call('sidequestion.continue', id='s2')
        self.assertIsNone(self.call('session.resume')['active_branch'])
    def test_future_explanation_surfaces_at_target_and_explicit_deepening_prevents_deferral(self):
        self.call('mainline.enter', concept_id='state', goal='States', next_step='Interpret psi')
        self.call('interaction.record', id='q', role='user', text='How will projection work?')
        self.call('sidequestion.open', id='future', interaction_id='q', category='future', depth='short', rationale='Projection is next', strategy='intuition', target_concept_id='projection')
        self.call('interaction.record', id='a', role='assistant', text='A coefficient measures overlap; the derivation follows later.')
        self.call('sidequestion.answer', id='future', answer_interaction_id='a')
        self.assertEqual(self.call('session.resume')['due_explanations'], [])
        entered = self.call('mainline.enter', concept_id='projection', goal='Projection', next_step='Derive overlap')
        self.assertEqual(entered['due_explanations'][0]['id'], 'future')
        self.assertEqual(self.call('session.resume')['due_explanations'][0]['status'], 'pending')
        self.call('interaction.record', id='full', role='assistant', text='The complete derivation...')
        self.call('deferred.resolve', id='future', answer_interaction_id='full')
        self.assertEqual(self.call('session.resume')['due_explanations'], [])
        self.call('interaction.record', id='deepq', role='user', text='Explain fully now.')
        self.call('sidequestion.open', id='deep', interaction_id='deepq', category='future', depth='short', rationale='Explicit request', strategy='derivation', target_concept_id='projection', explicit_deepen=True)
        self.call('interaction.record', id='deepa', role='assistant', text='Complete answer now.')
        self.call('sidequestion.answer', id='deep', answer_interaction_id='deepa')
        self.assertEqual(self.call('session.resume')['due_explanations'], [])
    def test_repeated_confusion_requires_changed_strategy_and_user_can_continue_without_gate(self):
        self.call('mainline.enter', concept_id='state', goal='States', next_step='Normalize')
        self.call('interaction.record', id='q1', role='user', text='Still unclear')
        self.call('sidequestion.open', error='invalid_strategy', id='repeat', interaction_id='q1', category='repeated', depth='long', rationale='Same difficulty returns', strategy='repeat_verbatim')
        self.call('sidequestion.open', id='repeat', interaction_id='q1', category='repeated', depth='long', rationale='Same difficulty returns', strategy='new_example')
        self.call('mainline.enter', error='active_branch', concept_id='projection', goal='Projection', next_step='Compute')
        self.call('sidequestion.continue', id='repeat')
        entered = self.call('mainline.enter', concept_id='projection', goal='Projection', next_step='Compute')
        self.assertEqual(entered['position']['concept_id'], 'projection')
        self.assertEqual(self.call('session.resume')['unanswered_questions'][0]['id'], 'repeat')
    def test_old_assistant_message_cannot_resolve_new_question(self):
        self.call('mainline.enter', concept_id='state', goal='States', next_step='Normalize')
        self.call('interaction.record', id='old', role='assistant', text='Unrelated older answer')
        self.call('interaction.record', id='newq', role='user', text='What is normalization?')
        self.call('sidequestion.open', id='branch', interaction_id='newq', category='local', depth='short', rationale='Definition', strategy='definition')
        self.call('sidequestion.answer', error='invalid_interaction', id='branch', answer_interaction_id='old')
        resumed = self.call('session.resume')
        self.assertEqual(resumed['active_branch']['status'], 'open')
        self.assertEqual(resumed['context']['concept']['id'], 'state')

    def test_future_followup_inside_waiting_branch_keeps_restore_point_and_surfaces_later(self):
        position = self.call('mainline.enter', concept_id='state', goal='Understand states', next_step='Normalize')['position']
        self.call('interaction.record', id='q2', role='user', text='Why is the state a function?', concept_id='state')
        self.call('sidequestion.open', id='bridge', interaction_id='q2', category='prerequisite', depth='long', rationale='Needed now', strategy='concept_bridge')
        self.call('interaction.record', id='a2', role='assistant', text='Coordinates describe a state in a chosen basis.', concept_id='state')
        self.call('sidequestion.answer', id='bridge', answer_interaction_id='a2')
        self.call('interaction.record', id='q3', role='user', text='Is changing basis related to Fourier transforms?', concept_id='projection')
        self.call('interaction.record', id='a3', role='assistant', text='Yes, it changes the basis; we will derive that with projection.', concept_id='projection')
        payload = dict(id='fourier-followup', interaction_id='q3', provisional_answer_interaction_id='a3', target_concept_id='projection')
        result = self.call('deferred.create', **payload)
        self.assertEqual(self.call('deferred.create', **payload), result)
        resumed = self.call('session.resume')
        self.assertEqual(resumed['active_branch']['status'], 'waiting')
        self.assertEqual(resumed['active_branch']['id'], 'bridge')
        self.assertEqual(resumed['active_branch']['restore_point'], position)
        self.assertEqual(resumed['position'], position)
        self.assertEqual(resumed['due_explanations'], [])
        self.call('interaction.record', id='continue', role='user', text='Continue')
        self.call('sidequestion.continue', id='bridge')
        due = self.call('mainline.enter', concept_id='projection', goal='Projection', next_step='Change basis')['due_explanations']
        self.assertEqual([item['id'] for item in due], ['fourier-followup'])
        self.call('interaction.record', id='full3', role='assistant', text='Here is the full Fourier derivation.', concept_id='projection')
        self.call('deferred.resolve', id='fourier-followup', answer_interaction_id='full3')
        self.call('deferred.create', **payload)
        self.assertEqual(self.call('session.resume')['due_explanations'], [])

    def test_deferred_creation_validates_sources_and_cannot_be_overwritten_by_auto_branch(self):
        self.call('mainline.enter', concept_id='state', goal='States', next_step='Normalize')
        self.call('interaction.record', id='old', role='assistant', text='Old answer')
        self.call('interaction.record', id='question', role='user', text='What about projection?')
        self.call('interaction.record', id='provisional', role='assistant', text='Overlap, more later.')
        payload = dict(id='promise', interaction_id='question', provisional_answer_interaction_id='provisional', target_concept_id='projection')
        self.call('deferred.create', **{**payload, 'target_concept_id':'missing'}, error='unknown_concept')
        self.call('deferred.create', **{**payload, 'interaction_id':'provisional'}, error='invalid_interaction')
        self.call('deferred.create', **{**payload, 'provisional_answer_interaction_id':'question'}, error='invalid_interaction')
        self.call('deferred.create', **{**payload, 'provisional_answer_interaction_id':'old'}, error='invalid_interaction')
        self.call('deferred.create', **payload)
        self.call('deferred.create', **{**payload, 'target_concept_id':'state'}, error='id_conflict')
        self.call('interaction.record', id='other-question', role='user', text='Another projection question')
        self.call('sidequestion.open', id='promise', interaction_id='other-question', category='future', depth='short', rationale='Later target', strategy='intuition', target_concept_id='projection')
        self.call('interaction.record', id='other-answer', role='assistant', text='Another provisional answer')
        self.call('sidequestion.answer', id='promise', answer_interaction_id='other-answer', error='id_conflict')
        self.assertEqual(self.call('session.resume')['active_branch']['status'], 'open')
        self.call('sidequestion.continue', id='promise')
        due = self.call('mainline.enter', concept_id='projection', goal='Projection', next_step='Derive')['due_explanations']
        self.assertEqual(due[0]['interaction_id'], 'question')
