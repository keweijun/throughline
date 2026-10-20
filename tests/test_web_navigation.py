import tempfile
import unittest
from pathlib import Path
from guided_learning.api import execute
from support import host_client


def source_path(ref, fmt=None):
    return f"/api/sources/{ref['source_id']}/{ref['revision']}/{ref['unit_id']}" + (f'?format={fmt}' if fmt else '')

class Navigation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        execute(self.root, {'op':'course.init','title':'Quantum course'})
        self.path=self.root/'notes.md'; self.path.write_text('# Original material\nThe squared magnitude of the amplitude gives the probability.',encoding='utf-8')
        self.source=execute(self.root,{'op':'source.register','path':str(self.path)})['source']
        self.ref={'source_id':self.source['id'],'revision':self.source['revision'],'unit_id':'line-2'}
        execute(self.root,{'op':'curriculum.save','concepts':[{'id':'wave','title':'Wave','objective':'Describe wave superposition'},{'id':'state','title':'Quantum state','objective':'Calculate measurement probabilities using amplitudes','prerequisites':['wave'],'links':[self.ref]}],'route':['wave','state'],'coverage':[]})
        execute(self.root,{'op':'position.save','request_id':'position','position':{'concept_id':'wave','goal':'Describe waves'}})
        self.client,self.host=host_client(self.root)
        self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None,None,None);self.tmp.cleanup()
    def get(self,path,status=200):
        response=self.client.get(path)
        self.assertEqual(response.status_code,status,response.text)
        return response.json()
    def test_preview_has_prerequisites_and_goal_without_moving_position(self):
        preview=self.get('/api/concepts/state/preview')
        self.assertEqual(preview['concept']['title'],'Quantum state')
        self.assertEqual(preview['prerequisites'][0]['id'],'wave')
        self.assertEqual(preview['overview']['target_ability'],'Calculate measurement probabilities using amplitudes')
        self.assertEqual(self.get('/api/state')['position']['concept_id'],'wave')

    def test_source_view_uses_exact_registered_revision_and_rejects_paths(self):
        self.path.write_text('changed on disk',encoding='utf-8')
        source=self.get(source_path(self.ref))
        self.assertEqual(source['text'],'The squared magnitude of the amplitude gives the probability.')
        self.assertEqual(source['locator'],{'line':2})
        self.assertEqual(source['verification'],'pending')
        self.assertEqual([u['id'] for u in source['document']],['line-1','line-2'])
        self.assertEqual(source['document'][0]['text'],'# Original material')
        for path in (source_path({**self.ref,'revision':'..%2Fnotes.md'}),source_path({**self.ref,'unit_id':'line-900'}),source_path(self.ref,'raw')):
            self.assertIn(self.client.get(path).status_code,(400,404,409),path)
        # A browser-supplied file path is never read; the registered revision is returned instead.
        self.assertEqual(self.get(source_path(self.ref)+'?path='+str(self.path))['text'],source['text'])
    def test_pdf_link_reads_original_revision_bytes_after_source_update(self):
        from pypdf import PdfWriter
        path=self.root/'lecture.pdf'; writer=PdfWriter();writer.add_blank_page(width=300,height=400)
        with path.open('wb') as f:writer.write(f)
        original=path.read_bytes(); source=execute(self.root,{'op':'source.register','path':str(path)})['source']
        ref={'source_id':source['id'],'revision':source['revision'],'unit_id':'page-1'}
        path.write_bytes(b'not a pdf anymore');execute(self.root,{'op':'source.register','path':str(path)})
        view=self.get(source_path(ref))
        self.assertTrue(view['stale']);self.assertTrue(view['pdf_url'].endswith('#page=1'))
        response=self.client.get(view['pdf_url'].split('#')[0])
        self.assertEqual(response.headers['content-type'],'application/pdf')
        self.assertEqual(response.content,original)
        self.assertIsNotNone(view['image_url'])
        response=self.client.get(view['image_url'])
        self.assertEqual(response.headers['content-type'],'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))
        saved=self.root/'sources'/source['id']/source['revision'];saved.write_bytes(b'tampered snapshot')
        self.get(source_path(ref),409)
    def test_first_lecture_requests_substantive_overview_in_same_generation(self):
        class Runner:
            def run(self,prompt,cwd,emit,cancel):
                if not hasattr(self, "prompt"):
                    self.prompt=prompt  # Capture mainline before automatic practice starts.
                emit({'kind':'final','text':'## Unit overview\nFrom wave superposition to measurement probabilities.'})
                emit({'kind':'complete'})
        runner=Runner();self.host._runner=runner
        self.host.start_turn({'id':'overview-test','concept_id':'wave','prompt':'Full explanation','channel':'mainline'})
        self.host.wait('overview-test',5)
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
        with patch('guided_learning.server.features.importlib.util.find_spec',return_value=None):
            view=self.get(source_path(ref))
            self.assertIsNone(view['image_url']);self.assertIn('unavailable',view['render_message'])
            self.assertEqual(self.client.get(view['pdf_url'].split('#')[0]).content,path.read_bytes())
            self.assertEqual(self.get(source_path(ref,'image'),409)['code'],'renderer_unavailable')
