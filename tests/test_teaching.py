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
