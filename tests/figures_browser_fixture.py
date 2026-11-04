"""A course whose PDF is partly read as pages (ADR 0019), with a lesson that shows a source figure, an unknown one and a
malformed one."""
from pathlib import Path
import tempfile

from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve
from tests.sample_pdf import write_pdf

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
course = root / 'course'
execute(course, {'op': 'course.init', 'title': 'Optics'})
pdf = root / 'lecture.pdf'
write_pdf(pdf, [['A thin lens focuses parallel rays.'], ['Mirrors']])
source = execute(course, {'op': 'source.register', 'path': str(pdf)})['source']
ref = {'source_id': source['id'], 'revision': source['revision']}
execute(course, {'op': 'source.readings.save', **ref, 'readings': [{'page': 1, 'text': 'A thin lens focuses parallel rays.', 'figures': [
    {'label': 'Figure 1.1', 'caption': 'Rays through a thin lens', 'description': 'Parallel rays bend through a convex lens and meet at its focus.',
     'box': [0, 0, 1, 0.3]}]}]})
figure = execute(course, {'op': 'source.read', 'source_id': source['id']})['units'][0]['figures'][0]['id']
execute(course, {'op': 'curriculum.save', 'concepts': [{'id': 'lens', 'title': 'Thin lenses', 'links': [{**ref, 'unit_id': 'page-1', 'detail': 'Lens'}]}],
                 'route': ['lens'], 'coverage': [{**ref, 'unit_id': 'page-1', 'disposition': 'mapped', 'concept_ids': ['lens']}]})
execute(course, {'op': 'widgets.save', 'ids': ['figure']})

FENCE = '`' * 3
LESSON = f'''Parallel rays meet at the focus.

{FENCE}figure
{figure}
{FENCE}

Look where the rays cross.

{FENCE}figure
fig-0000000000
{FENCE}

{FENCE}figure
not a figure
{FENCE}
'''


class Runner:
    def run(self, prompt, cwd, emit, cancel, images=()):
        text = LESSON + ('\n<lesson-step>{"remaining": []}</lesson-step>' if 'This reply teaches step' in prompt else '')
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(course, port=0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
