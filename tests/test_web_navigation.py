import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from guided_learning.api import execute
from guided_learning.web import create_server

class Navigation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        execute(self.root, {'op':'course.init','title':'Quantum course'})
        self.path=self.root/'notes.md'; self.path.write_text('# Original material\nThe squared magnitude of the amplitude gives the probability.',encoding='utf-8')
        self.source=execute(self.root,{'op':'source.register','path':str(self.path)})['source']
        self.ref={'source_id':self.source['id'],'revision':self.source['revision'],'unit_id':'line-2'}
        execute(self.root,{'op':'curriculum.save','concepts':[{'id':'wave','title':'Wave','objective':'Describe wave superposition'},{'id':'state','title':'Quantum state','objective':'Calculate measurement probabilities using amplitudes','prerequisites':['wave'],'links':[self.ref]}],'route':['wave','state'],'coverage':[]})
        execute(self.root,{'op':'position.save','request_id':'position','position':{'concept_id':'wave','goal':'Describe waves'}})
        self.server=create_server(self.root,port=0)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.tmp.cleanup()
    def get(self,path):
        with urlopen(self.base+path) as response: return json.load(response)
    def test_preview_has_prerequisites_and_goal_without_moving_position(self):
        preview=self.get('/api/navigation/preview?concept_id=state')
        self.assertEqual(preview['concept']['title'],'Quantum state')
        self.assertEqual(preview['prerequisites'][0]['id'],'wave')
        self.assertEqual(preview['overview']['target_ability'],'Calculate measurement probabilities using amplitudes')
        self.assertEqual(self.get('/api/state')['position']['concept_id'],'wave')

    def test_source_view_uses_exact_registered_revision_and_rejects_paths(self):
        self.path.write_text('changed on disk',encoding='utf-8')
        source=self.get('/api/navigation/source?'+urlencode(self.ref))
        self.assertEqual(source['text'],'The squared magnitude of the amplitude gives the probability.')
        self.assertEqual(source['locator'],{'line':2})
        self.assertEqual(source['verification'],'pending')
        for query in ({**self.ref,'revision':'../notes.md'},{**self.ref,'unit_id':'line-900'},{'path':str(self.path)}):
            with self.assertRaises(HTTPError) as error:
                self.get('/api/navigation/source?'+urlencode(query))
            self.assertIn(error.exception.code,(400,409)); error.exception.close()
    def test_pdf_link_reads_original_revision_bytes_after_source_update(self):
        from pypdf import PdfWriter
        path=self.root/'lecture.pdf'; writer=PdfWriter();writer.add_blank_page(width=300,height=400)
        with path.open('wb') as f:writer.write(f)
        original=path.read_bytes(); source=execute(self.root,{'op':'source.register','path':str(path)})['source']
        ref={'source_id':source['id'],'revision':source['revision'],'unit_id':'page-1'}
        path.write_bytes(b'not a pdf anymore');execute(self.root,{'op':'source.register','path':str(path)})
        view=self.get('/api/navigation/source?'+urlencode(ref))
        self.assertTrue(view['stale']);self.assertTrue(view['pdf_url'].endswith('#page=1'))
        with urlopen(self.base+view['pdf_url'].split('#')[0]) as response:
            self.assertEqual(response.headers.get_content_type(),'application/pdf')
            self.assertEqual(response.read(),original)
        self.assertIsNotNone(view['image_url'])
        with urlopen(self.base+view['image_url']) as response:
            self.assertEqual(response.headers.get_content_type(),'image/png')
            self.assertTrue(response.read().startswith(b'\x89PNG\r\n\x1a\n'))
        saved=self.root/'sources'/source['id']/source['revision'];saved.write_bytes(b'tampered snapshot')
        with self.assertRaises(HTTPError) as error:self.get('/api/navigation/source?'+urlencode(ref))
        self.assertEqual(error.exception.code,409);error.exception.close()
    def test_first_lecture_requests_substantive_overview_in_same_generation(self):
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                if not hasattr(self, "prompt"):
                    self.prompt=prompt  # Capture mainline before automatic practice starts.
                emit({'kind':'final','text':'## Unit overview\nFrom wave superposition to measurement probabilities.'})
                emit({'kind':'complete'})
        runner=Runner();self.server.app.runner=runner
        self.server.app.start_turn({'id':'overview-test','concept_id':'wave','prompt':'Full explanation','channel':'mainline'})
        self.server.app.wait('overview-test',5)
        self.assertIn('core problem',runner.prompt)
        self.assertIn('target ability',runner.prompt)
        self.assertIn('Unit overview',runner.prompt)

    def test_missing_pdf_renderer_is_explicit_and_original_remains_available(self):
        from pypdf import PdfWriter
        from unittest.mock import patch
        path=self.root/'plain.pdf';writer=PdfWriter();writer.add_blank_page(width=300,height=400)
        with path.open('wb') as file:writer.write(file)
        source=execute(self.root,{'op':'source.register','path':str(path)})['source']
        ref={'source_id':source['id'],'revision':source['revision'],'unit_id':'page-1'}
        with patch('guided_learning.web_navigation.importlib.util.find_spec',return_value=None):
            view=self.get('/api/navigation/source?'+urlencode(ref))
            self.assertIsNone(view['image_url']);self.assertIn('unavailable',view['render_message'])
            with urlopen(self.base+view['pdf_url'].split('#')[0]) as response:self.assertEqual(response.read(),path.read_bytes())
            with self.assertRaises(HTTPError) as error:self.get('/api/navigation/source?'+urlencode({**ref,'image':'1'}))
            self.assertEqual(json.load(error.exception)['code'],'renderer_unavailable');error.exception.close()
