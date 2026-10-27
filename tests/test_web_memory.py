import json
import tempfile
import unittest

from guided_learning.api import execute
from guided_learning.server import Host
from support import host_client

LESSON = ('A plane wave is $e^{ikx}$.\n<course-memory>{"entries":[{"kind":"taught_term","text":"plane wave"},'
          '{"kind":"preference","text":"One step at a time"}],"cleared":[]}</course-memory>')
ANSWER = ('Amplitudes add before squaring.\n<teaching-decision>{"depth":"short","category":"local","rationale":"local","suggest_supplement":false,'
          '"supplement_goal":""}</teaching-decision>\n<course-memory>{"entries":[{"kind":"taught_term","text":"amplitude"}]}</course-memory>')


class Runner:
    def __init__(self):
        self.prompts = []
        self.assessment = {}

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if 'Branch decision protocol' in prompt:
            text = ANSWER
        elif 'Practice only: return JSON {"questions"' in prompt:
            text = '{"questions":[{"question":"Normalize $e^{ikx}$ on a box.","origin":"self_created","source_refs":[]}]}'
        elif 'Assess the reasoning' in prompt:
            text = json.dumps(self.assessment)
        else:
            text = LESSON
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}], 'route': ['state'], 'coverage': []})
    execute(path, {'op': 'mainline.enter', 'concept_id': 'state', 'goal': 'states', 'next_step': 'read', 'request_id': 'p'})


def settle(app):
    for turn in app.brief_turns():
        app.wait(turn['id'], 5)


class MemoryFlow(unittest.TestCase):
    def test_teaching_turns_write_memory_and_later_prompts_carry_what_is_in_effect(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'annotations.save', 'id': 'n', 'kind': 'note', 'concept_id': 'state', 'note': 'PRIVATE-NOTE'})
            runner = Runner()
            app = Host(path, runner=runner)
            try:
                app.start_turn({'id': 'one', 'concept_id': 'state', 'prompt': 'Teach'})
                settle(app)
                self.assertIn('<course-memory>', runner.prompts[0])
                entries = {e['kind']: e for e in app.operation({'op': 'memory.view'})['entries']}
                self.assertEqual(entries['taught_term']['interaction_ids'], ['stream-user:one', 'stream:one'])
                self.assertEqual(entries['preference']['status'], 'suggested')

                app.questions.ask({'id': 'q', 'question': 'Why add amplitudes?', 'main_turn_id': 'one'})
                settle(app)
                self.assertEqual(app.operation({'op': 'branch.read', 'id': 'q'})['branch']['decision']['category'], 'local')
                snapshot = app.operation({'op': 'stream.read', 'id': 'branch:q'})['turn']['prompt_snapshot']
                self.assertEqual(snapshot['course_memory'], {'taught_terms': [{'term': 'plane wave', 'concept_id': 'state'}]})
                self.assertIn('amplitude', [e['text'] for e in app.operation({'op': 'memory.view'})['entries']])

                task = app.practice.state()['tasks'][0]
                runner.assessment = {'feedback': 'The norm is wrong again.', 'outcome': 'needs_work',
                                     'memory': {'entries': [{'kind': 'difficulty', 'text': 'Normalizing over a finite box'}]}}
                app.practice.act(task['id'], 'assess', 'N = 1')
                settle(app)
                difficulty = next(e for e in app.operation({'op': 'memory.view'})['entries'] if e['kind'] == 'difficulty')
                self.assertTrue(all(i.startswith(('practice-answer:', 'practice-feedback:')) for i in difficulty['interaction_ids']))

                app.operation({'op': 'memory.confirm', 'id': entries['preference']['id']})
                runner.assessment = {'feedback': 'Correct.', 'outcome': 'passed', 'memory': {'entries': [], 'cleared': [difficulty['id']]}}
                app.practice.act(task['id'], 'assess', 'N = 1/sqrt(L)')
                settle(app)
                self.assertEqual(next(e for e in app.operation({'op': 'memory.view'})['entries'] if e['kind'] == 'difficulty')['status'], 'cleared')

                app.start_turn({'id': 'two', 'concept_id': 'state', 'prompt': 'Again'})
                settle(app)
                snapshot = app.operation({'op': 'stream.read', 'id': 'two'})['turn']['prompt_snapshot']
                self.assertEqual(snapshot['course_memory']['preferences'], ['One step at a time'])
                self.assertNotIn('difficulties', snapshot['course_memory'])
                self.assertTrue(all('PRIVATE-NOTE' not in p for p in runner.prompts))
            finally:
                app.close()

    def test_memory_routes_view_edit_confirm_and_delete(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'memory.note', 'turn_id': 't', 'concept_id': 'state', 'interaction_ids': [],
                           'note': {'entries': [{'kind': 'preference', 'text': 'Give the tedious integrals'}, {'kind': 'taught_term', 'text': 'ket'}]}})
            client, host = host_client(path, runner=Runner())
            with client:
                memory = client.get('/api/state').json()['memory']
                preference = next(e for e in memory if e['kind'] == 'preference')
                term = next(e for e in memory if e['kind'] == 'taught_term')
                self.assertEqual(client.put(f'/api/memory/{term["id"]}', json={'text': 'bra-ket'}).json()['entry']['text'], 'bra-ket')
                self.assertEqual(client.post(f'/api/memory/{preference["id"]}/confirm').json()['entry']['status'], 'confirmed')
                self.assertEqual(client.post(f'/api/memory/{term["id"]}/confirm').status_code, 409)
                self.assertEqual(client.delete(f'/api/memory/{term["id"]}').status_code, 200)
                self.assertEqual(client.delete(f'/api/memory/{term["id"]}').status_code, 404)
                self.assertEqual(client.put(f'/api/memory/{preference["id"]}', json={'text': 'x', 'kind': 'difficulty'}).status_code, 400)
                self.assertEqual([e['text'] for e in client.get('/api/state').json()['memory']], ['Give the tedious integrals'])


class Consolidating:
    """Answers a consolidation turn with `reply` and records which turns ran on the small model."""

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def runner(self, small=False):
        settings = self

        class Run:
            def run(self, prompt, cwd, emit, cancel):
                settings.calls.append((small, prompt))
                if 'Consolidate the course memory' not in prompt:
                    text = 'Prepared.'
                elif isinstance(settings.reply, Exception):
                    raise settings.reply
                else:
                    text = settings.reply if isinstance(settings.reply, str) else json.dumps(settings.reply)
                emit({'kind': 'final', 'text': text})
                emit({'kind': 'complete'})
        return Run()


def remembered(path):
    execute(path, {'op': 'course.init', 'title': 'Quantum'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'state', 'title': 'States'}, {'id': 'spin', 'title': 'Spin'}],
                   'route': ['state', 'spin'], 'coverage': []})
    execute(path, {'op': 'mainline.enter', 'concept_id': 'state', 'goal': 'states', 'next_step': 'read', 'request_id': 'p'})
    execute(path, {'op': 'interaction.record', 'id': 'i1', 'role': 'user', 'text': 'q', 'concept_id': 'state'})
    def note(turn, entries, cleared=()):
        return execute(path, {'op': 'memory.note', 'turn_id': turn, 'concept_id': 'state', 'interaction_ids': ['i1'] if turn == 't1' else [],
                              'note': {'entries': entries, 'cleared': list(cleared)}})['recorded']
    [term, difficulty, preference, gone] = note('t1', [{'kind': 'taught_term', 'text': 'plane wave'}, {'kind': 'difficulty', 'text': 'Box normalization'},
                                                       {'kind': 'preference', 'text': 'One step at a time'}, {'kind': 'taught_term', 'text': 'DELETED-TERM'}])
    [plural] = note('t2', [{'kind': 'taught_term', 'text': 'plane waves'}], cleared=[difficulty['id']])
    execute(path, {'op': 'memory.confirm', 'id': preference['id']})
    execute(path, {'op': 'memory.delete', 'id': gone['id']})
    return {'term': term['id'], 'plural': plural['id'], 'difficulty': difficulty['id'], 'preference': preference['id'], 'deleted': gone['id']}


class SectionEndConsolidation(unittest.TestCase):
    def run_consolidation(self, path, reply):
        settings = Consolidating(reply)
        app = Host(path, settings=settings)
        try:
            app.practice.next_section('state', 'r1')
            settle(app)
            return app, settings
        finally:
            app.close()

    def test_entering_the_next_section_consolidates_the_previous_one_on_the_small_model(self):
        with tempfile.TemporaryDirectory() as path:
            ids = remembered(path)
            app, settings = self.run_consolidation(path, {'merge': [{'into': ids['term'], 'entries': [ids['plural']]}],
                                                          'prune': [{'id': ids['difficulty'], 'reason': 'Cleared in practice'}]})
            turn = app.operation({'op': 'stream.read', 'id': 'consolidation-state'})['turn']
            self.assertEqual((turn['channel'], turn['concept_id'], turn['status']), ('consolidation', 'state', 'completed'))
            [(small, prompt)] = [c for c in settings.calls if 'Consolidate the course memory' in c[1]]
            self.assertTrue(small)
            self.assertIn(ids['plural'], prompt)
            self.assertNotIn('DELETED-TERM', prompt)
            entries = {e['id']: e for e in app.operation({'op': 'memory.view'})['entries']}
            self.assertEqual(set(entries), {ids['term'], ids['preference']})
            self.assertEqual(entries[ids['preference']]['status'], 'confirmed')
            self.assertEqual(app.operation({'op': 'memory.consolidations'})['consolidations'][0]['turn_id'], 'consolidation-state')
            self.assertEqual(app.operation({'op': 'course.status'})['position']['concept_id'], 'spin')
            # Background work, not a teaching interaction.
            self.assertNotIn('stream:consolidation-state', [i['id'] for i in app.operation({'op': 'session.resume', 'recent_limit': 20})['recent_interactions']])

            # One consolidation per section.
            app = Host(path, settings=settings)
            try:
                self.assertFalse(app.memory.consolidate('state')['created'])
                settle(app)
            finally:
                app.close()
            self.assertEqual(len([c for c in settings.calls if 'Consolidate the course memory' in c[1]]), 1)

    def test_a_refused_or_failed_consolidation_leaves_memory_unchanged(self):
        for reply in ('not json', RuntimeError('model down'),
                      {'merge': [], 'entries': [{'kind': 'preference', 'text': 'Be brief'}]},
                      'DELETED', 'CONFIRMED'):
            with self.subTest(reply=reply), tempfile.TemporaryDirectory() as path:
                ids = remembered(path)
                if reply == 'DELETED':
                    reply = {'merge': [{'into': ids['term'], 'entries': [ids['deleted']]}]}
                elif reply == 'CONFIRMED':
                    reply = {'prune': [{'id': ids['difficulty'], 'reason': 'Cleared'}, {'id': ids['preference'], 'reason': 'stale'}]}
                before = execute(path, {'op': 'memory.view'})['entries']
                app, _ = self.run_consolidation(path, reply)
                status = app.operation({'op': 'stream.read', 'id': 'consolidation-state'})['turn']['status']
                self.assertEqual(status, 'failed' if isinstance(reply, Exception) else 'completed')
                self.assertEqual(app.operation({'op': 'memory.view'})['entries'], before)
                self.assertEqual(app.operation({'op': 'memory.consolidations'})['consolidations'], [])


if __name__ == '__main__':
    unittest.main()
