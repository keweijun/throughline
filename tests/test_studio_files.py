"""Files Codex links to in a Studio reply: a course source opens in the reader, any other file on this computer."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from support import call_cli
from guided_learning.files import Opener
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings


class StudioFiles(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.tmp = Path(scratch.name).resolve()  # macOS and Windows hand out temp paths through links and short names
        self.library = self.tmp / 'library'
        self.course = self.library / 'waves'
        self.course.mkdir(parents=True)
        call_cli(self, self.course, 'course.init', title='Waves')
        (self.course / 'inputs').mkdir()
        self.notes = self.course / 'inputs' / 'notes.md'
        self.notes.write_text('one\ntwo\nthree\n', encoding='utf-8')
        self.source = call_cli(self, self.course, 'source.register', path=str(self.notes))['source']
        self.started = []
        self.client = self.open(self.course, Opener(platform='linux', start=self.started.append))

    def open(self, course, opener):
        app = create_app(course, runner=None, settings=TeacherSettings(self.tmp / 'config' / 'settings.json'),
                         library_root=self.library, opener=opener)
        client = TestClient(app, base_url='http://127.0.0.1:8765')
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return client

    def post(self, path, line=None, scope=''):
        response = self.client.post(f'/api/studio/files/open?scope={scope}', json={'path': path, 'line': line})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def ref(self, unit):
        return {'source': {'source_id': self.source['id'], 'revision': self.source['revision'], 'unit_id': unit}}

    def test_a_course_source_opens_in_the_reader_at_its_line(self):
        self.assertEqual(self.post(str(self.notes), 2), self.ref('line-2'))
        self.assertEqual(self.post(str(self.notes)), self.ref('line-1'))
        self.assertEqual(self.post(str(self.notes), 40), self.ref('line-1'), 'a line past the end opens at the start')
        # Relative links are read from the library folder, where Studio's Codex works.
        self.assertEqual(self.post('waves/inputs/notes.md', 3), self.ref('line-3'))
        self.assertEqual(self.started, [])

    def test_a_converted_document_opens_as_its_pdf(self):
        original = self.course / 'inputs' / 'slides.pptx'
        original.write_bytes(b'deck')
        pdf = self.course / 'inputs' / 'slides.pdf'
        pdf.write_bytes(b'%PDF-1.4 not really')
        registered = call_cli(self, self.course, 'source.register', path=str(pdf), converted_from=str(original))['source']
        self.assertEqual(self.post(str(original), 5)['source'],
                         {'source_id': registered['id'], 'revision': registered['revision'], 'unit_id': 'page-1'})

    def test_other_files_open_on_this_computer(self):
        outline = self.course / 'outline.md'
        outline.write_text('# Outline', encoding='utf-8')
        self.assertEqual(self.post(str(outline), 4), {'opened': str(outline), 'shown': False})
        self.assertEqual(self.started[-1], ['xdg-open', str(outline)])
        # The library's Studio has no course, so even a source opens in its own app.
        self.assertEqual(self.post(str(self.notes), scope='library'), {'opened': str(self.notes), 'shown': False})

    def test_programs_and_missing_files_are_shown_in_their_folder(self):
        script = self.course / 'build.sh'
        script.write_text('echo hi', encoding='utf-8')
        self.assertEqual(self.post(str(script)), {'opened': str(script), 'shown': True})
        self.assertEqual(self.started[-1], ['xdg-open', str(self.course)])
        self.assertEqual(self.post(str(self.course / 'gone' / 'x.md')), {'opened': str(self.course), 'shown': True})
        self.assertEqual(self.started[-1], ['xdg-open', str(self.course)])

    def test_commands_on_windows_and_macos(self):
        script = self.course / 'build.sh'
        script.write_text('echo hi', encoding='utf-8')
        for platform, document, program in [
            ('nt', ['explorer', str(self.notes)], ['explorer', f'/select,{script}']),
            ('darwin', ['open', str(self.notes)], ['open', '-R', str(script)]),
        ]:
            started = []
            opener = Opener(platform=platform, start=started.append)
            opener.open(self.notes)
            opener.open(script)
            self.assertEqual(started, [document, program], platform)

    def test_a_bad_request_is_refused(self):
        self.assertEqual(self.client.post('/api/studio/files/open', json={'path': ''}).status_code, 400)
        self.assertEqual(self.client.post('/api/studio/files/open', json={'path': 'x.md', 'line': 0}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
