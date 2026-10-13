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
