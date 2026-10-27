import tempfile
import unittest
from pathlib import Path
from guided_learning.api import execute


def course(tmp):
    execute(tmp, {'op': 'course.init', 'title': 'Q'})
    execute(tmp, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B', 'objective': 'Explain interference'}],
                  'route': ['a', 'b'], 'coverage': []})
    execute(tmp, {'op': 'mainline.enter', 'concept_id': 'a', 'goal': 'A', 'next_step': 'B', 'request_id': 'p'})


class Runner:
    """Answers side questions with a future deferral and records every prompt it was given."""
    def __init__(self, target='b'):
        self.prompts = []
        self.target = target
        self.lessons = []

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        if 'Branch decision protocol' in prompt:
            text = ('Short: phase matters later.\n<teaching-decision>{"depth":"short","category":"future","rationale":"interference later",'
                    '"suggest_supplement":false,"supplement_goal":"","target_concept_id":"' + self.target + '"}</teaching-decision>')
        else:
            text = self.lessons.pop(0) if self.lessons else 'A full lesson.\n<lesson-step>{"remaining": []}</lesson-step>'  # one step ends the lesson
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


class Continuity(unittest.TestCase):
    def test_pending_explanation_is_taught_and_resolved_in_its_target_section(self):
        from guided_learning.server import Host
        runner = Runner()
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            app = Host(tmp, runner=runner)
            try:
                app.questions.ask({'id': 'q', 'question': 'Why does phase matter?'})
                app.wait('branch:q', 3)
                [item] = app.snapshot()['deferred_explanations']
                self.assertEqual((item['status'], item['target_concept_id']), ('pending', 'b'))
                self.assertEqual(item['question'], 'Why does phase matter?')
                self.assertIn('phase matters later', item['provisional_answer'])

                app.practice.next_section('a', 'n')
                self.assertEqual(app.snapshot()['position']['goal'], 'Explain interference')
                app.start_lesson({'id': 'lesson-b'})
                app.wait('lesson-b', 3)
                lesson_prompt = next(p for p in runner.prompts if 'Pending explanations' in p)
                self.assertIn('Why does phase matter?', lesson_prompt)

                [item] = app.snapshot()['deferred_explanations']
                self.assertEqual(item['status'], 'resolved')
                self.assertEqual(item['answer_interaction_id'], 'stream:lesson-b')
                self.assertEqual(app.snapshot()['session']['due_explanations'], [])
            finally:
                app.close()

    def test_a_stepped_lesson_resolves_pending_explanations_with_its_last_step(self):
        from guided_learning.server import Host
        runner = Runner()
        runner.lessons = ['Step one.\n<lesson-step>{"remaining": [{"title": "Phase"}]}</lesson-step>', 'Step two.\n<lesson-step>{"remaining": []}</lesson-step>']
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            app = Host(tmp, runner=runner)
            try:
                app.questions.ask({'id': 'q', 'question': 'Why does phase matter?'})
                app.wait('branch:q', 3)
                app.practice.next_section('a', 'n')
                app.start_lesson({'id': 'one'})
                app.wait('one', 3)
                self.assertEqual(app.snapshot()['deferred_explanations'][0]['status'], 'pending')
                app.navigation.continue_lesson('one', {'id': 'two'})
                app.wait('two', 3)
                self.assertIn('Pending explanations', next(p for p in runner.prompts if 'teaches step 2' in p))
                [item] = app.snapshot()['deferred_explanations']
                self.assertEqual((item['status'], item['answer_interaction_id']), ('resolved', 'stream:two'))
            finally:
                app.close()

    def test_lesson_outside_target_section_does_not_resolve_explanation(self):
        from guided_learning.server import Host
        runner = Runner()
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            app = Host(tmp, runner=runner)
            try:
                app.questions.ask({'id': 'q', 'question': 'Why does phase matter?'})
                app.wait('branch:q', 3)
                app.start_lesson({'id': 'lesson-a'})
                app.wait('lesson-a', 3)
                self.assertFalse(any('Pending explanations' in p for p in runner.prompts))
                self.assertEqual(app.snapshot()['deferred_explanations'][0]['status'], 'pending')
            finally:
                app.close()

    def test_unknown_target_section_keeps_route_note_without_scheduling(self):
        from guided_learning.server import Host
        with tempfile.TemporaryDirectory() as tmp:
            course(tmp)
            app = Host(tmp, runner=Runner(target='nowhere'))
            try:
                app.questions.ask({'id': 'q', 'question': 'Why?'})
                app.wait('branch:q', 3)
                branch = app.operation({'op': 'branch.read', 'id': 'q'})['branch']
                self.assertEqual(branch['status'], 'answered')
                self.assertEqual(branch['decision']['category'], 'future')
                self.assertIsNone(branch['decision']['target_concept_id'])
                self.assertEqual(app.snapshot()['deferred_explanations'], [])
            finally:
                app.close()

    def test_preview_lists_set_aside_material_for_the_section(self):
        from guided_learning.server import Host
        with tempfile.TemporaryDirectory() as tmp:
            execute(tmp, {'op': 'course.init', 'title': 'Q'})
            path = Path(tmp) / 'notes.md'
            path.write_text('first line\nsecond line', encoding='utf-8')
            source = execute(tmp, {'op': 'source.register', 'path': str(path)})['source']
            ref = {'source_id': source['id'], 'revision': source['revision']}
            execute(tmp, {'op': 'curriculum.save', 'concepts': [{'id': 'a', 'title': 'A', 'links': [{**ref, 'unit_id': 'line-1'}]}], 'route': ['a'],
                          'coverage': [{**ref, 'unit_id': 'line-1', 'disposition': 'mapped', 'concept_ids': ['a']},
                                       {**ref, 'unit_id': 'line-2', 'disposition': 'deferred', 'concept_ids': ['a'], 'reason': 'Proof is optional'}]})
            app = Host(tmp, runner=Runner())
            try:
                [item] = app.navigation.preview('a')['set_aside']
                self.assertEqual((item['unit_id'], item['disposition'], item['reason']), ('line-2', 'deferred', 'Proof is optional'))
            finally:
                app.close()


if __name__ == '__main__':
    unittest.main()
