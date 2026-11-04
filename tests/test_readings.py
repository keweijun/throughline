"""Page readings (ADR 0019): Codex reads PDF pages as images, and the reading stands in for the extracted text."""
from support import ROOT, call_cli
from sample_pdf import write_pdf
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def has_pdf_extra():
    try:
        import pypdf, pypdfium2, PIL  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(has_pdf_extra(), 'Install the pdf extra for page readings')
class PageReadings(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.course = self.base / 'course'
        self.call('course.init', title='Optics')
        self.pdf = self.base / 'lecture.pdf'
        write_pdf(self.pdf, [['Snell law n1 sin a = n2 sin b'], ['Lens figure page'], [], ['Problems']])
        self.source = self.call('source.register', path=str(self.pdf))['source']
        self.ref = {'source_id': self.source['id'], 'revision': self.source['revision']}

    def call(self, op, error=None, **fields):
        return call_cli(self, self.course, op, error=error, **fields)

    def reading(self, page, **fields):
        return {'page': page, 'text': f'Reading of page {page}', **fields}

    LENS = {'label': 'Figure 2.1', 'caption': 'A thin lens', 'description': 'Rays through a convex lens meet at the focus F.', 'box': [0.1, 0.2, 0.9, 0.6]}

    def test_a_reading_replaces_the_extracted_text_for_the_teacher_but_not_for_search(self):
        snell = r'Snell: $n_1 \sin\alpha = n_2 \sin\beta$'
        result = self.call('source.readings.save', **self.ref, readings=[{'page': 1, 'text': snell}, self.reading(2, figures=[self.LENS])])
        self.assertEqual(result['saved'], [1, 2])
        self.assertEqual(result['readings'], {'pages': 4, 'read': 2, 'unread': [[3, 4]], 'problems': []})

        units = self.call('source.read', source_id=self.source['id'])['units']
        self.assertEqual(units[0]['text'], snell)
        self.assertEqual((units[0]['verification'], units[0]['reading']), ('verified', True))
        figure = units[1]['figures'][0]
        self.assertTrue(figure['id'].startswith('fig-'))
        self.assertEqual({k: figure[k] for k in ('label', 'caption', 'description')}, {k: self.LENS[k] for k in ('label', 'caption', 'description')})
        self.assertNotIn('box', figure)  # where it sits matters to the interface, not the teacher
        self.assertEqual((units[3]['text'].strip(), units[3]['verification']), ('Problems', 'pending'))

        excerpt = self.call('source.units', refs=[{**self.ref, 'unit_id': 'page-1'}])['sources'][0]['unit']
        self.assertEqual(excerpt['text'], snell)
        found = self.call('source.search', query='Snell law')['units']
        self.assertEqual([u['unit_id'] for u in found], ['page-1'])
        self.assertIn('n1 sin a', found[0]['excerpt'])

        status = self.call('course.status')['sources'][0]
        self.assertEqual((status['pages'], status['pages_read'], status['problem_pages'], status['verification']), (4, 2, 0, 'pending'))

    def test_a_fully_read_source_is_verified_and_a_read_scanned_page_no_longer_needs_review(self):
        concept = {'id': 'refraction', 'title': 'Refraction', 'prerequisites': [], 'links': [{**self.ref, 'unit_id': 'page-3', 'detail': 'Scanned page'}]}
        self.call('curriculum.save', concepts=[concept], route=['refraction'],
                  coverage=[{**self.ref, 'unit_id': 'page-3', 'disposition': 'mapped', 'concept_ids': ['refraction']}])
        page3 = next(u for u in self.call('curriculum.coverage')['units'] if u['unit_id'] == 'page-3')
        self.assertEqual(page3['disposition'], 'needs_review')

        self.call('source.readings.save', **self.ref, readings=[self.reading(n) for n in (1, 2, 4)] + [self.reading(3, problems=['The bottom margin is cut off'])])
        page3 = next(u for u in self.call('curriculum.coverage')['units'] if u['unit_id'] == 'page-3')
        self.assertEqual(page3['disposition'], 'mapped')
        context = self.call('curriculum.context', concept_id='refraction')['sources'][0]
        self.assertEqual((context['text'], context['problems']), ('Reading of page 3', ['The bottom margin is cut off']))

        read = self.call('source.read', source_id=self.source['id'])
        self.assertEqual(read['verification'], 'verified')
        self.assertEqual(read['readings'], {'pages': 4, 'read': 4, 'unread': [], 'problems': [[3, 3]]})
        status = self.call('course.status')['sources'][0]
        self.assertEqual((status['pages_read'], status['problem_pages'], status['verification']), (4, 1, 'verified'))

    def test_reading_a_page_again_replaces_its_reading_and_figures(self):
        first = self.call('source.readings.save', **self.ref, readings=[self.reading(2, figures=[self.LENS, {**self.LENS, 'label': 'Figure 2.2'}])])
        ids = [f['id'] for f in self.call('source.read', source_id=self.source['id'])['units'][1]['figures']]
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(self.call('source.figure', id=ids[1])['figure']['label'], 'Figure 2.2')
        self.assertEqual(first['readings']['read'], 1)

        self.call('source.readings.save', **self.ref, readings=[{'page': 2, 'text': 'Corrected', 'figures': [{**self.LENS, 'caption': 'A thin convex lens'}]}])
        unit = self.call('source.read', source_id=self.source['id'])['units'][1]
        self.assertEqual(unit['text'], 'Corrected')
        self.assertEqual([f['id'] for f in unit['figures']], ids[:1])  # ids follow the position on the page
        found = self.call('source.figure', id=ids[0])['figure']
        self.assertEqual((found['caption'], found['page'], found['unit_id'], found['box']), ('A thin convex lens', 2, 'page-2', self.LENS['box']))
        self.call('source.figure', error='unknown_figure', id=ids[1])

    def test_invalid_readings_are_refused_whole(self):
        bad = [
            [self.reading(5)],
            [self.reading(1), self.reading(1)],
            [self.reading(1, figures=[{**self.LENS, 'box': [0.5, 0.2, 0.4, 0.6]}])],
            [self.reading(1, figures=[{**self.LENS, 'description': ' '}])],
            [self.reading(1, problems=[''])],
            [],
        ]
        for readings in bad:
            self.call('source.readings.save', error='invalid_reading' if readings else 'invalid_request', **self.ref, readings=readings)
        self.call('source.readings.save', error='invalid_reading', **self.ref, readings=[self.reading(1), self.reading(9)])
        self.assertEqual(self.call('source.read', source_id=self.source['id'])['readings']['read'], 0)

        notes = self.base / 'notes.md'
        notes.write_text('Exact text', encoding='utf-8')
        text_source = self.call('source.register', path=str(notes))['source']
        self.call('source.readings.save', error='invalid_request', source_id=text_source['id'], readings=[self.reading(1)])
        self.assertNotIn('readings', self.call('source.read', source_id=text_source['id']))

    def test_readings_saved_at_the_same_time_all_land(self):
        processes = [subprocess.Popen([sys.executable, '-m', 'guided_learning', '--workspace', str(self.course)], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, text=True, cwd=ROOT)
                     for _ in range(4)]
        for page, process in enumerate(processes, 1):
            process.stdin.write(json.dumps({'op': 'source.readings.save', **self.ref, 'readings': [self.reading(page)]}))
            process.stdin.close()
        for process in processes:
            self.assertTrue(json.loads(process.stdout.read())['ok'])
            process.stdout.close()
            process.wait()
        self.assertEqual(self.call('source.read', source_id=self.source['id'])['readings']['read'], 4)

    def test_pages_boxes_and_figures_render_to_files(self):
        from PIL import Image
        out = self.base / 'renders'
        images = self.call('source.render', **self.ref, pages=[1, 2], size=600, out=str(out))['images']
        self.assertEqual([i['page'] for i in images], [1, 2])
        with Image.open(images[0]['path']) as page:
            self.assertEqual(max(page.size), 600)
            self.assertAlmostEqual(page.size[0] / page.size[1], 612 / 792, places=2)

        box = self.call('source.render', **self.ref, page=2, box=[0, 0, 0.5, 0.25], size=400, out=str(out))['images'][0]
        with Image.open(box['path']) as crop:
            self.assertEqual(max(crop.size), 400)
            self.assertAlmostEqual(crop.size[0] / crop.size[1], (612 * 0.5) / (792 * 0.25), places=1)

        self.call('source.readings.save', **self.ref, readings=[self.reading(2, figures=[self.LENS])])
        fid = self.call('source.read', source_id=self.source['id'])['units'][1]['figures'][0]['id']
        drawn = self.call('source.render', figures=[fid])['images'][0]
        self.assertEqual((drawn['figure'], drawn['page']), (fid, 2))
        self.assertTrue(Path(drawn['path']).is_relative_to(self.course / 'page_images'))
        with Image.open(drawn['path']) as crop:
            self.assertAlmostEqual(crop.size[0] / crop.size[1], (612 * 0.8) / (792 * 0.4), places=1)

        self.call('source.render', error='invalid_request', **self.ref, pages=[5])
        self.call('source.render', error='invalid_request', **self.ref, page=1, box=[0, 0, 0, 1])
        self.call('source.render', error='invalid_request', **self.ref, page=1, size=50)
        self.call('source.render', error='unknown_figure', figures=['fig-0000000000'])


if __name__ == '__main__':
    unittest.main()
