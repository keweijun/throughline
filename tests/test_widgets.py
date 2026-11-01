import tempfile
import unittest

from guided_learning.api import execute
from guided_learning.server import Host
from support import call_cli, settle


class Runner:
    def __init__(self):
        self.prompts = []

    def run(self, prompt, cwd, emit, cancel):
        self.prompts.append(prompt)
        emit({'kind': 'final', 'text': 'A limit is approached, not reached.'})
        emit({'kind': 'complete'})


def course(path):
    execute(path, {'op': 'course.init', 'title': 'Calculus'})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'limits', 'title': 'Limits'}], 'route': ['limits'], 'coverage': []})
    execute(path, {'op': 'mainline.enter', 'concept_id': 'limits', 'goal': 'limits', 'next_step': 'read', 'request_id': 'p'})


class Selection(unittest.TestCase):
    def test_a_course_starts_with_no_add_ons_and_saves_a_selection_in_library_order(self):
        with tempfile.TemporaryDirectory() as path:
            call_cli(self, path, 'course.init', title='Chemistry')
            listed = call_cli(self, path, 'widgets.list')
            self.assertEqual(listed['selected'], [])
            self.assertEqual({'plot', 'chemistry', 'python'}, {item['id'] for item in listed['library']})
            self.assertTrue(all(item['summary'] and item['subjects'] for item in listed['library']))
            saved = call_cli(self, path, 'widgets.save', ids=['chemistry', 'plot', 'plot'])
            self.assertEqual(saved['selected'], ['plot', 'chemistry'])
            self.assertEqual(call_cli(self, path, 'widgets.save', ids=[])['selected'], [])

    def test_unknown_add_ons_and_malformed_requests_change_nothing(self):
        with tempfile.TemporaryDirectory() as path:
            call_cli(self, path, 'course.init', title='Chemistry')
            call_cli(self, path, 'widgets.save', ids=['plot'])
            error = call_cli(self, path, 'widgets.save', error='unknown_widget', ids=['plot', 'geogebra'])
            self.assertIn('geogebra', error['error']['message'])
            call_cli(self, path, 'widgets.save', error='invalid_request', ids='plot')
            self.assertEqual(call_cli(self, path, 'widgets.list')['selected'], ['plot'])


class Prompts(unittest.TestCase):
    def teach(self, path, turn):
        runner = Runner()
        app = Host(path, runner=runner)
        try:
            app.start_turn({'id': turn, 'concept_id': 'limits', 'prompt': 'Teach'})
            settle(app)
        finally:
            app.close()
        return runner.prompts[0]

    def test_the_teacher_always_learns_the_basics_and_only_the_selected_add_ons(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            prompt = self.teach(path, 'before')
            self.assertIn('```mermaid', prompt)
            self.assertIn('[!WARNING]', prompt)
            self.assertNotIn('```plot', prompt)
            self.assertNotIn(r'\ce{', prompt)

            execute(path, {'op': 'widgets.save', 'ids': ['plot']})
            prompt = self.teach(path, 'after')
            self.assertIn('```plot', prompt.instructions)
            self.assertNotIn('```plot', prompt.request)
            self.assertNotIn(r'\ce{', prompt)
            self.assertEqual(execute(path, {'op': 'stream.read', 'id': 'after'})['turn']['prompt_snapshot']['widgets'], ['plot'])

    def test_a_turn_keeps_the_add_ons_it_started_with(self):
        with tempfile.TemporaryDirectory() as path:
            course(path)
            execute(path, {'op': 'widgets.save', 'ids': ['chemistry']})
            self.teach(path, 'one')
            execute(path, {'op': 'widgets.save', 'ids': []})
            self.assertEqual(execute(path, {'op': 'stream.read', 'id': 'one'})['turn']['prompt_snapshot']['widgets'], ['chemistry'])
            self.assertNotIn(r'\ce{', self.teach(path, 'two'))
            self.assertNotIn('widgets', execute(path, {'op': 'stream.read', 'id': 'two'})['turn']['prompt_snapshot'])


if __name__ == '__main__':
    unittest.main()
