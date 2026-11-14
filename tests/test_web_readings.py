"""Page readings in teaching (ADR 0019): preparation sees the figures and problem pages, and lessons show figures."""
import tempfile
import time
import unittest
from pathlib import Path

from guided_learning.api import execute
from sample_pdf import write_pdf
from support import host_client
from test_readings import has_pdf_extra


class Runner:
    def __init__(self):
        self.calls = []

    def run(self, prompt, cwd, emit, cancel, images=()):
        self.calls.append((str(prompt), list(images)))
        emit({'kind': 'final', 'text': 'Prepared' if 'Internal preparation task' in prompt else 'Taught'})
        emit({'kind': 'complete'})


def course(path, base):
    def op(**kw):
        return execute(path, kw)
    op(op='course.init', title='Optics')
    pdf = Path(base) / 'lecture.pdf'
    write_pdf(pdf, [['Lens diagram'], ['Smudged page'], ['Plain page']])
    source = op(op='source.register', path=str(pdf))['source']
    ref = {'source_id': source['id'], 'revision': source['revision']}
    op(op='source.readings.save', **ref, readings=[
        {'page': 1, 'text': 'A lens', 'figures': [{'label': 'Figure 1', 'caption': 'A thin lens', 'description': 'Rays meet at F.', 'box': [0, 0, 0.5, 0.5]}]},
        {'page': 2, 'text': 'Most of page 2', 'problems': ['The last equation is smudged']},
        {'page': 3, 'text': 'Plain'}])
    links = [{**ref, 'unit_id': f'page-{n}', 'detail': 'Lenses'} for n in (1, 2, 3)]
    op(op='curriculum.save', concepts=[{'id': 'a', 'title': 'Lenses', 'links': links}, {'id': 'b', 'title': 'Mirrors', 'links': links}],
       route=['a', 'b'], coverage=[])
    op(op='mainline.enter', request_id='enter', concept_id='a', goal='Lenses', next_step='explain')
    figure = op(op='source.read', source_id=source['id'])['units'][0]['figures'][0]['id']
    return source, figure


@unittest.skipUnless(has_pdf_extra(), 'Install the pdf extra for page readings')
class ReadingsInTeaching(unittest.TestCase):
    def test_preparation_and_an_unprepared_first_lesson_see_figures_and_problem_pages(self):
        with tempfile.TemporaryDirectory() as path, tempfile.TemporaryDirectory() as base:
            source, figure = course(path, base)
            runner = Runner()
            client, host = host_client(path, runner=runner)
            with client:
                # Section a has no preparation material, so its first lesson prepares itself and sees the figures.
                first = host.start_turn({'concept_id': 'a', 'channel': 'mainline', 'prompt': 'Teach'})['turn']
                host.wait(first['id'], 5)
                prompt, images = runner.calls[0]
                self.assertIn('Image inputs, in order: figure', prompt)
                self.assertEqual(len(images), 2)

                # With a lesson started, the next section is prepared, and its preparation sees the same images.
                deadline = time.time() + 5
                while time.time() < deadline and not any('Internal preparation task' in p for p, _ in runner.calls):
                    time.sleep(.05)
                prompt, images = next(c for c in runner.calls if 'Internal preparation task' in c[0])
                self.assertIn(f'Image inputs, in order: figure {figure} (Figure 1) on page 1; page 2 of source {source["id"]}, whose reading lists problems', prompt)
                self.assertEqual(len(images), 2)
                self.assertTrue(all(Path(p).read_bytes().startswith(b'\x89PNG') for p in images))
                self.assertIn(figure, Path(images[0]).name)
                for request in ({'concept_id': 'a', 'channel': 'mainline', 'prompt': 'Again'},
                                {'concept_id': 'a', 'channel': 'sidequestion', 'prompt': 'Why?'}):
                    turn = host.start_turn(request)['turn']
                    host.wait(turn['id'], 5)
                    prompt, images = runner.calls[-1]
                    self.assertEqual(images, [])
                    self.assertNotIn('Image inputs', prompt)

    def test_a_figure_is_served_with_its_caption_and_as_a_crop(self):
        with tempfile.TemporaryDirectory() as path, tempfile.TemporaryDirectory() as base:
            source, figure = course(path, base)
            client, host = host_client(path, runner=Runner())
            with client:
                shown = client.get(f'/api/figures/{figure}').json()
                self.assertEqual((shown['label'], shown['caption'], shown['page'], shown['title']), ('Figure 1', 'A thin lens', 1, 'lecture.pdf'))
                self.assertEqual(shown['ref'], {'source_id': source['id'], 'revision': source['revision'], 'unit_id': 'page-1'})
                image = client.get(shown['image_url'])
                self.assertEqual(image.headers['content-type'], 'image/png')
                self.assertTrue(image.content.startswith(b'\x89PNG'))
                self.assertEqual(client.get('/api/figures/fig-0000000000').status_code, 404)
                self.assertEqual(client.get(f'/api/figures/{figure}?format=pdf').status_code, 409)


if __name__ == '__main__':
    unittest.main()
