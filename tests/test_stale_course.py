"""A page acts only on the course it loaded: another course opened since, in another tab say, refuses its requests
(`X-Throughline-Course`, docs/architecture.md)."""
import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from guided_learning.api import execute
from guided_learning.server import Host, create_app
from guided_learning.server.settings import TeacherSettings


class Idle:
    def run(self, prompt, cwd, emit, cancel):
        emit({'kind': 'final', 'text': 'Prepared'})
        emit({'kind': 'complete'})


def course(path, title):
    # Both courses have a section with the same ID, so a note meant for one fits the other.
    execute(path, {'op': 'course.init', 'title': title})
    execute(path, {'op': 'curriculum.save', 'concepts': [{'id': 'intro', 'title': 'Introduction'}], 'route': ['intro'], 'coverage': []})


def notes(path):
    return [a['note'] for a in execute(path, {'op': 'annotations.list'})['annotations']]


class StalePages(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        config = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, config, ignore_errors=True)
        course(self.root / 'alpha', 'Alpha')
        course(self.root / 'beta', 'Beta')
        self.app = create_app(port=8765, runner=Idle(), settings=TeacherSettings(config / 's.json'), library_root=self.root)
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8765')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.client.post('/api/library/open', json={'name': 'alpha'})
        self.alpha = self.client.get('/api/state').json()['course']['key']
        self.client.post('/api/library/open', json={'name': 'beta'})  # in another tab
        self.beta = self.client.get('/api/state').json()['course']['key']

    def note(self, course):
        return self.client.post('/api/annotations', json={'kind': 'note', 'concept_id': 'intro', 'note': 'Meant for Alpha'},
                                headers={'X-Throughline-Course': course})

    def test_a_note_from_a_page_of_another_course_is_refused_and_saved_nowhere(self):
        response = self.note(self.alpha)
        self.assertEqual((response.status_code, response.json()['code']), (409, 'course_changed'))
        self.assertEqual(notes(self.root / 'beta'), [], 'the open course takes nothing from the stale page')
        self.assertEqual(notes(self.root / 'alpha'), [])
        self.assertEqual(self.note(self.beta).status_code, 200, "the open course's own page still writes")
        self.assertEqual(notes(self.root / 'beta'), ['Meant for Alpha'])

    def test_a_share_names_its_course_so_another_open_course_never_answers_for_it(self):
        # Sharing is done from a course's card in the library, which names the course, whichever one is open.
        shared = self.client.get('/api/library/courses/alpha/package/everything')
        self.assertEqual(shared.status_code, 200)
        self.assertIn('alpha.throughline', shared.headers['content-disposition'])

    def test_reads_of_the_state_are_refused_too(self):
        self.assertEqual(self.client.get('/api/state', headers={'X-Throughline-Course': self.alpha}).json()['code'], 'course_changed')
        self.assertEqual(self.client.get('/api/state?only=memory', headers={'X-Throughline-Course': self.alpha}).status_code, 409)

    def test_a_copy_of_a_course_folder_is_another_course(self):
        # The learner copied alpha's folder while it was closed; the copy keeps alpha's ID.
        shutil.copytree(self.root / 'alpha', self.root / 'alpha-copy')
        self.client.post('/api/library/open', json={'name': 'alpha-copy'})  # in another tab
        response = self.note(self.alpha)
        self.assertEqual((response.status_code, response.json()['code']), (409, 'course_changed'))
        self.assertEqual(notes(self.root / 'alpha-copy'), [], 'a page of the original writes nothing into the copy')
        stale = self.client.get('/api/state?course=' + self.alpha)
        self.assertEqual(stale.status_code, 409, "nor reads the copy's records")
        copy = self.client.get('/api/state').json()['course']['key']
        self.assertEqual(self.note(copy).status_code, 200)

    def test_a_page_whose_course_was_closed_is_told_the_course_changed(self):
        self.client.delete('/api/library/courses/beta')
        response = self.client.get('/api/state', headers={'X-Throughline-Course': self.beta})
        self.assertEqual((response.status_code, response.json()['code']), (409, 'course_changed'))

    def test_library_wide_routes_answer_a_stale_page(self):
        stale = {'X-Throughline-Course': self.alpha}
        for path in ('/api/library', '/api/settings', '/api/seen', '/api/health', '/api/about', '/api/studio?scope=library'):
            self.assertEqual(self.client.get(path, headers=stale).status_code, 200, path)
        opened = self.client.post('/api/library/open', json={'name': 'alpha'}, headers={'X-Throughline-Course': self.beta})
        self.assertEqual(opened.status_code, 200, 'a page may open another course')

    def test_a_request_without_a_course_acts_on_the_open_one(self):
        response = self.client.post('/api/annotations', json={'kind': 'note', 'concept_id': 'intro', 'note': 'Unnamed'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(notes(self.root / 'beta'), ['Unnamed'])

    def test_a_course_switch_while_a_request_runs_leaves_it_on_its_course(self):
        courses = self.app.state.courses
        beta = courses.host
        operation = Host.operation

        def switching(host, request):
            if request['op'] == 'annotations.list' and host is beta:
                courses.open_named('alpha')  # between checking the note's ID and saving it
            return operation(host, request)
        Host.operation = switching
        self.addCleanup(setattr, Host, 'operation', operation)
        self.assertEqual(self.note(self.beta).status_code, 200)
        self.assertEqual(notes(self.root / 'beta'), ['Meant for Alpha'])
        self.assertEqual(notes(self.root / 'alpha'), [])

    def test_events_name_the_course_they_are_for(self):
        host = self.app.state.courses.host
        seen = []

        async def collect():
            subscriber = host.events.subscribe()
            host.changed('memory')
            seen.append(await asyncio.wait_for(subscriber[1].get(), 5))
            host.events.unsubscribe(subscriber)
        asyncio.run(collect())
        self.assertEqual(seen, [{'type': 'changed', 'scope': 'memory', 'course': self.beta}])


if __name__ == '__main__':
    unittest.main()
