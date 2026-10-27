"""`/api/state` carries only what the interface reads (issue #62); domain operations keep every field."""
import asyncio
import tempfile
import unittest
from pathlib import Path

from guided_learning.api import execute
from guided_learning.server import Host
from support import host_client


class BlockingRunner:
    def run(self, prompt, cwd, emit, cancel):
        cancel.wait(3)


def course(path):
    def op(**kw):
        return execute(path, kw)
    op(op='course.init', title='Quantum')
    notes = Path(path) / 'notes.md'
    notes.write_text('Amplitudes\nProbabilities\n', encoding='utf-8')
    source = op(op='source.register', path=str(notes))['source']
    ref = {'source_id': source['id'], 'revision': source['revision'], 'unit_id': 'line-1'}
    concepts = [
        {'id': 'a', 'title': 'Amplitudes', 'prerequisites': [], 'objective': 'Add amplitudes',
         'links': [{**ref, 'detail': 'Amplitudes', 'review_note': 'Checked against the PDF'}],
         'exercises': [{**ref, 'question': 'Q1(a)', 'part_of': 'Q1', 'placement_reason': 'build audit', 'required_concepts': ['a'],
                        'other_parts': [{'question': 'Q1(b)', 'concept_id': 'b', 'split_note': 'audit'}]}],
         'teaching_plan': ['Long build-time plan'] * 20, 'coverage_checklist': [{'item': 'x'}], 'verification_notes': 'audit'},
        {'id': 'b', 'title': 'Probabilities', 'prerequisites': ['a']},
    ]
    coverage = [{**ref, 'disposition': 'mapped', 'concept_ids': ['a'], 'verification': 'verified', 'verification_note': 'audit'}]
    op(op='curriculum.save', concepts=concepts, route=['a', 'b'], coverage=coverage)
    op(op='mainline.enter', request_id='enter', concept_id='a', goal='Add amplitudes', next_step='Read')
    op(op='stream.start', id='lesson', concept_id='a', prompt='Explain amplitudes')
    op(op='stream.event', id='lesson', attempt=1, sequence=1, kind='delta', text='Amplitudes add.')
    op(op='stream.event', id='lesson', attempt=1, sequence=2, kind='final', text='Amplitudes add.')
    op(op='stream.event', id='lesson', attempt=1, sequence=3, kind='complete')
    op(op='preparation.enqueue', id='prep')
    op(op='stream.start', id='prep', concept_id='b', prompt='Internal prep', channel='preparation', record_user=False)
    op(op='stream.event', id='prep', attempt=1, sequence=1, kind='final', text='Prepared material')
    op(op='stream.event', id='prep', attempt=1, sequence=2, kind='complete')
    return op, concepts, coverage


class SlimState(unittest.TestCase):
    def test_state_projects_build_time_fields_snapshots_and_duplicate_text_away(self):
        with tempfile.TemporaryDirectory() as tmp:
            op, concepts, coverage = course(tmp)
            client, host = host_client(tmp, runner=BlockingRunner())
            with client:
                state = client.get('/api/state').json()
                ref = {k: concepts[0]['links'][0][k] for k in ('source_id', 'revision', 'unit_id')}
                self.assertEqual(state['curriculum']['concepts'], [
                    {'id': 'a', 'title': 'Amplitudes', 'prerequisites': [], 'objective': 'Add amplitudes', 'links': [ref],
                     'exercises': [{**ref, 'question': 'Q1(a)', 'part_of': 'Q1', 'other_parts': [{'question': 'Q1(b)', 'concept_id': 'b'}]}]},
                    {'id': 'b', 'title': 'Probabilities', 'prerequisites': ['a']}])
                self.assertEqual(state['curriculum']['coverage'], [{**ref, 'disposition': 'mapped', 'concept_ids': ['a'], 'verification': 'verified'}])
                self.assertEqual(state['curriculum']['route'], ['a', 'b'])
                self.assertEqual([c['concept_ids'] for c in state['curriculum']['chapters']], [['a', 'b']])

                job = next(j for j in state['preparation']['jobs'] if j['id'] == 'prep')
                self.assertEqual(set(job), {'id', 'concept_id', 'status', 'created_at'})
                self.assertEqual((job['concept_id'], job['status']), ('b', 'ready'))
                self.assertEqual(state['preparation']['next_concept_id'], 'b')
                full = op(op='preparation.view', concept_id='b')
                self.assertIn('snapshot', full['jobs'][0], 'the operation itself is unchanged')
                brief = op(op='preparation.view', concept_id='b', brief=True)
                self.assertEqual(brief, {**full, 'jobs': [{k: v for k, v in j.items() if k not in ('snapshot', 'content')} for j in full['jobs']],
                                         'ready': {k: v for k, v in full['ready'].items() if k not in ('snapshot', 'content')}})

                lesson = next(t for t in state['turns'] if t['id'] == 'lesson')
                self.assertEqual(lesson['text'], 'Amplitudes add.')
                self.assertFalse({'final_text', 'metrics', 'prompt', 'prompt_snapshot'} & set(lesson))
                self.assertEqual(lesson['source_refs'], [ref])
                prep = next(t for t in state['turns'] if t['id'] == 'prep')
                self.assertEqual((prep['status'], prep['text'], prep['attempts'], prep['source_refs']), ('completed', '', [], []),
                                 'background turns are never shown, so their text stays on the host')

                self.assertEqual(set(state['session']), {'recent_interactions'})
                self.assertEqual({'id', 'role', 'text', 'concept_id'}, set(state['session']['recent_interactions'][-1]))
                self.assertNotIn('profile', state)
                self.assertTrue({'course', 'position', 'sources', 'preferences', 'deferred_explanations', 'lessons', 'questions',
                                 'practice', 'review', 'settings', 'annotations', 'memory', 'skipped', 'builds'} <= set(state))

    def test_curriculum_version_follows_fields_the_projection_leaves_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            op, concepts, coverage = course(tmp)
            client, host = host_client(tmp, runner=BlockingRunner())
            with client:
                before = client.get('/api/state').json()['curriculum']
                self.assertEqual(client.get('/api/state').json()['curriculum']['version'], before['version'])
                concepts[0]['teaching_plan'] = ['Revised plan']
                op(op='curriculum.save', concepts=concepts, route=['a', 'b'], coverage=coverage)
                after = client.get('/api/state').json()['curriculum']
                self.assertEqual(after['concepts'], before['concepts'])
                self.assertNotEqual(after['version'], before['version'], 'the section preview reads the whole plan')

    def test_state_parts_load_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            client, host = host_client(tmp, runner=BlockingRunner())
            with client:
                state = client.get('/api/state').json()
                self.assertEqual(client.get('/api/state?only=preparation').json(), {'preparation': state['preparation']})
                self.assertEqual(client.get('/api/state?only=preparation,settings,memory,builds').json(),
                                 {k: state[k] for k in ('preparation', 'settings', 'memory', 'builds')})
                self.assertEqual(client.get('/api/state?only=turns').status_code, 400, 'only parts the interface reloads alone')

    def test_turn_events_carry_one_text(self):
        class Runner:
            def run(self, prompt, cwd, emit, cancel):
                if 'Practice' in prompt.split('Current learner request:')[-1]:
                    return
                emit({'kind': 'delta', 'text': 'Hello '})
                emit({'kind': 'final', 'text': 'Hello lesson.'})
                emit({'kind': 'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op': 'course.init', 'title': 'Quantum'})
            execute(tmp, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'A'}], 'route': ['a'], 'coverage': []})
            host = Host(tmp, runner=Runner())
            seen = []

            async def collect():
                subscriber = host.events.subscribe()
                await asyncio.to_thread(host.start_lesson, {'id': 'live'})
                while True:
                    event = await asyncio.wait_for(subscriber[1].get(), 5)
                    if event['type'] == 'turn' and event['turn']['id'] == 'live':
                        seen.append(event['turn'])
                        if event['turn']['status'] == 'completed':
                            return
            try:
                asyncio.run(collect())
            finally:
                host.close()
            self.assertEqual(seen[-1]['text'], 'Hello lesson.')
            self.assertFalse({'final_text', 'metrics', 'prompt'} & set(seen[-1]))

    def test_finished_preparation_changes_only_preparation(self):
        class Runner:
            def run(self, prompt, cwd, emit, cancel):
                emit({'kind': 'final', 'text': 'Prepared material'})
                emit({'kind': 'complete'})
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op': 'course.init', 'title': 'Quantum'})
            execute(tmp, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B'}], 'route': ['a', 'b'], 'coverage': []})
            execute(tmp, {'op': 'mainline.enter', 'request_id': 'enter', 'concept_id': 'a', 'goal': 'A', 'next_step': 'Read'})
            host = Host(tmp, runner=Runner())
            seen = []

            async def collect():
                subscriber = host.events.subscribe()
                done = False
                while True:
                    event = await asyncio.wait_for(subscriber[1].get(), 5)
                    if done and event['type'] == 'changed':
                        seen.append(event['scope'])
                        return
                    done = done or event['type'] == 'turn' and event['turn']['channel'] == 'preparation' and event['turn']['status'] == 'completed'
            try:
                asyncio.run(collect())
            finally:
                host.close()
            self.assertEqual(seen, ['preparation'], 'the interface reloads only the preparation, not the whole state')


if __name__ == '__main__':
    unittest.main()
