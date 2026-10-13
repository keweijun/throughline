import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class EvidenceCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = self.temp.name
        self.call('course.init', title='Quantum')
        self.call('curriculum.save', concepts=[{'id':'state','title':'State'}, {'id':'projection','title':'Projection'}], route=['state','projection'])

    def call(self, op, error=None, **fields):
        proc = subprocess.run([sys.executable, '-m', 'guided_learning', '--workspace', self.workspace], input=json.dumps({'op':op, **fields}), text=True, encoding='utf-8', capture_output=True, cwd=ROOT)
        response = json.loads(proc.stdout)
        if error:
            self.assertEqual(response['error']['code'], error, response)
            return response
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return response['result']

    def say(self, id, role, text):
        return self.call('interaction.record', id=id, role=role, text=text, concept_id='state')

    def test_exposure_and_self_report_never_become_independent_evidence(self):
        self.say('teacher', 'assistant', 'A state gives amplitudes.')
        self.say('learner', 'user', 'I understand, continue.')
        self.call('evidence.record', id='taught', concept_id='state', kind='taught', interaction_id='teacher')
        self.call('evidence.record', id='self', concept_id='state', kind='self_report', interaction_id='learner')
        state = self.call('evidence.view', concept_id='state')
        self.assertEqual(state['status'], 'self_reported')
        self.assertEqual(len(state['history']), 2)
        self.assertFalse(state['independently_verified'])
        self.call('evidence.record', id='bad', concept_id='state', kind='independent', interaction_id='teacher', error='invalid_evidence')

    def test_hints_constrain_independent_claims_and_assessments_need_learner_answers(self):
        self.say('hint', 'assistant', 'Try expanding in the eigenbasis.')
        self.say('answer', 'user', 'The coefficient is the inner product.')
        self.say('review', 'assistant', 'Correct: the inner product extracts the component.')
        self.call('evidence.record', id='h1', concept_id='state', kind='hint', interaction_id='hint', session_id='s1', exercise_id='q1', level='minimal')
        fields = dict(id='a1', concept_id='state', session_id='s1', exercise_id='q1', answer_id='answer', assessment_id='review', outcome='passed')
        result = self.call('evidence.assess', **fields)
        self.assertEqual(result['evidence']['kind'], 'hinted')
        self.assertEqual(result['evidence']['hint_ids'], ['h1'])
        self.assertEqual(self.call('evidence.assess', **fields), result)
        self.call('evidence.assess', **{**fields, 'outcome':'needs_work'}, error='id_conflict')
        self.call('evidence.assess', **{**fields, 'id':'wrong', 'answer_id':'hint'}, error='invalid_evidence')
        self.assertEqual(self.call('evidence.view', concept_id='state')['status'], 'hinted')

    def test_retest_requires_prior_independent_pass_and_new_session(self):
        self.say('answer', 'user', 'The amplitude is an inner product.')
        self.say('review', 'assistant', 'Correct with no assistance.')
        base = dict(concept_id='state', exercise_id='q2', answer_id='answer', assessment_id='review', outcome='passed')
        self.call('evidence.assess', id='first', session_id='s1', **base)
        self.assertTrue(self.call('evidence.view', concept_id='state')['independently_verified'])
        self.say('answer2', 'user', 'For this new basis I compute the overlap.')
        self.say('review2', 'assistant', 'Correct transfer to the new basis.')
        later = {**base, 'answer_id':'answer2', 'assessment_id':'review2', 'retest_of':'first'}
        self.call('evidence.assess', id='retry', session_id='s1', **later, error='invalid_evidence')
        result = self.call('evidence.assess', id='retry', session_id='s2', **later)
        self.assertEqual(result['evidence']['kind'], 'retest_passed')
        self.assertEqual(self.call('evidence.view', concept_id='state')['status'], 'retest_passed')
        self.call('evidence.assess', id='reuse', session_id='s3', **later, error='invalid_evidence')

    def test_skips_stay_unverified_and_only_revisit_at_target_or_recap(self):
        self.call('evidence.defer', id='skip', concept_id='state', reason='Continue now', target_concept_id='projection', section_id='section1')
        self.call('evidence.defer', id='skip', concept_id='state', reason='Continue now', target_concept_id='projection', section_id='section1')
        self.assertEqual(self.call('evidence.view', concept_id='state')['status'], 'unverified')
        self.assertEqual(self.call('evidence.review', concept_id='state')['due'], [])
        review = self.call('evidence.review', concept_id='projection')
        self.assertEqual([d['id'] for d in review['due']], ['skip'])
        self.assertFalse(review['quiz_required'])
        recap = self.call('evidence.review', concept_id='state', section_id='section1', recap=True)
        self.assertEqual(len(recap['due']), 1)
        self.assertEqual(recap['practice_policy'], 'concentrated_at_section_end; minimal_hint_first; full_solution_on_request')
        self.call('evidence.defer', id='skip', concept_id='state', reason='Changed', target_concept_id='projection', error='id_conflict')

    def test_deferred_resolution_preserves_history_without_repeated_reminders(self):
        self.call('evidence.defer', id='skip', concept_id='state', reason='Later', target_concept_id='projection')
        self.say('revisit', 'user', 'I have now reviewed the definition.')
        self.call('evidence.resolve', id='resolved', deferred_id='skip', interaction_id='revisit')
        self.assertEqual(self.call('evidence.review', concept_id='projection')['due'], [])
        self.assertEqual(self.call('evidence.view', concept_id='state')['status'], 'unverified')
        history = self.call('evidence.review', concept_id='state')
        self.assertEqual(history['deferred_history'][0]['id'], 'skip')
        self.assertEqual(history['resolutions'][0]['interaction_id'], 'revisit')

    def test_complete_solution_counts_as_exposure_and_later_failures_remain_visible(self):
        self.say('solution', 'assistant', 'Here is the complete worked solution.')
        self.call('evidence.record', id='demo', kind='demonstrated', concept_id='state', interaction_id='solution', session_id='s1', exercise_id='q1')
        self.assertEqual(self.call('evidence.view', concept_id='state')['status'], 'taught')
        self.say('attempt1', 'user', 'My independent solution for a different exercise.')
        self.say('assessment1', 'assistant', 'Correct calculation.')
        self.call('evidence.assess', id='p', concept_id='state', session_id='s2', exercise_id='q2', answer_id='attempt1', assessment_id='assessment1', outcome='passed')
        self.say('attempt2', 'user', 'My next solution has an error.')
        self.say('assessment2', 'assistant', 'This misses normalization.')
        self.call('evidence.assess', id='f', concept_id='state', session_id='s3', exercise_id='q3', answer_id='attempt2', assessment_id='assessment2', outcome='needs_work')
        state = self.call('evidence.view', concept_id='state')
        self.assertTrue(state['independently_verified'])
        self.assertEqual(state['latest_assessment']['kind'], 'needs_work')

    def test_later_hints_do_not_rewrite_prior_assessments_and_late_import_is_rejected(self):
        self.say('earlyhint', 'assistant', 'An earlier hint.')
        self.say('answer', 'user', 'Initial answer.')
        self.say('assessment', 'assistant', 'Needs normalization.')
        fields = dict(id='a', concept_id='state', session_id='s', exercise_id='q', answer_id='answer', assessment_id='assessment', outcome='needs_work')
        original = self.call('evidence.assess', **fields)
        self.call('evidence.record', id='lateimport', concept_id='state', kind='hint', interaction_id='earlyhint', session_id='s', exercise_id='q', level='minimal', error='invalid_evidence')
        self.say('laterhint', 'assistant', 'Now check normalization.')
        self.call('evidence.record', id='h', concept_id='state', kind='hint', interaction_id='laterhint', session_id='s', exercise_id='q', level='minimal')
        self.assertEqual(self.call('evidence.assess', **fields), original)
