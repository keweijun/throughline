import json
import tempfile
from pathlib import Path
import unittest

from guided_learning.api import execute
from guided_learning.server import Host
from guided_learning.server.settings import TeacherSettings
from support import host_client, settle

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
                for rule in ('Use a taught term without defining it again', 'Derive or justify an example',
                             'Mention source verification or extraction quality only when',
                             'the term itself in a few words'):
                    self.assertIn(rule, runner.prompts[0])
                self.assertNotIn('State uncertainty about formulas', runner.prompts[0])
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

    def test_the_learner_tells_the_teacher_what_to_remember(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'memory.note', 'turn_id': 't', 'concept_id': 'state', 'interaction_ids': [],
                           'note': {'entries': [{'kind': 'preference', 'text': 'Long derivations'}]}})
            [old] = execute(path, {'op': 'memory.view'})['entries']
            settings = Answering({'reply': 'I will keep answers short and stop writing out long derivations.',
                                  'remember': ['Short answers first'], 'forget': [old['id']]})
            client, host = host_client(path, settings=settings)
            with client:
                asked = client.post('/api/memory', json={'text': 'Please keep it short, no long derivations', 'concept_id': 'state'}).json()['request']
                settle(host)
                state = client.get('/api/state').json()
                [request] = state['memory_requests']
                self.assertEqual((request['id'], request['reply']), (asked['id'], 'I will keep answers short and stop writing out long derivations.'))
                [entry] = state['memory']
                self.assertEqual((entry['text'], entry['status'], entry['concept_id']), ('Short answers first', 'confirmed', None))
                self.assertEqual(entry['interaction_ids'], ['memory-request:' + asked['id']])
                self.assertEqual(request['remembered'], [entry['id']])
                self.assertEqual(request['forgotten'], [old['id']])
            [(small, prompt)] = settings.calls
            self.assertTrue(small)
            self.assertIn('Please keep it short', prompt)
            self.assertIn(old['id'], prompt)
            self.assertEqual(execute(path, {'op': 'memory.prompt'})['memory']['preferences'], ['Short answers first'])
            # The request is the learner's message, not a teaching exchange.
            recent = [i['id'] for i in execute(path, {'op': 'session.resume', 'recent_limit': 20})['recent_interactions']]
            self.assertNotIn('stream:' + asked['turn_id'], recent)

    def test_a_malformed_memory_reply_changes_nothing_and_says_why(self):
        for reply in ('not json', {'reply': 'ok', 'remember': 'Short answers'}, {'reply': 'ok', 'forget': ['unknown']}, {'remember': ['x']}):
            with self.subTest(reply=reply), tempfile.TemporaryDirectory() as path:
                course(path)
                client, host = host_client(path, settings=Answering(reply))
                with client:
                    client.post('/api/memory', json={'text': 'Short answers please', 'concept_id': 'state'})
                    settle(host)
                    state = client.get('/api/state').json()
                    self.assertEqual(state['memory'], [])
                    self.assertTrue(state['memory_requests'][0]['error'])


class Answering(TeacherSettings):
    """Answers every turn with `reply` and records whether it ran on the small model."""

    def __init__(self, reply):
        super().__init__(Path(tempfile.mkdtemp()) / 'settings.json')
        self.reply, self.calls = reply, []

    def runner(self, small=False):
        settings = self

        class Run:
            def run(self, prompt, cwd, emit, cancel):
                settings.calls.append((small, prompt))
                emit({'kind': 'final', 'text': settings.reply if isinstance(settings.reply, str) else json.dumps(settings.reply)})
                emit({'kind': 'complete'})
        return Run()


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
