"""A long course for judging the route at real scale: python -m tests.long_course_browser_fixture [port].

Twelve built chapters of uneven length (130 sections, one chapter of 30) and an outlined chapter not built yet; the
first 40 sections have completed lessons and the learner is at section 41.
"""
import sys
import tempfile
from pathlib import Path
from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Mathematical Methods for Physics'})

SIZES = [6, 9, 14, 8, 30, 10, 12, 7, 15, 11, 5, 3]
TITLES = ['Vectors', 'Complex numbers', 'Calculus of several variables', 'Matrices', 'Linear algebra',
          'Fourier series', 'Fourier transforms', 'Ordinary differential equations', 'Partial differential equations',
          'Special functions', 'Probability', 'Tensors']
chapters = [{'id': f'ch{n}', 'title': title} for n, title in enumerate(TITLES, 1)] + [{'id': 'ch13', 'title': 'Group theory'}]
execute(root, {'op': 'curriculum.outline', 'chapters': chapters})
route = []
for n, size in enumerate(SIZES, 1):
    concepts = [{'id': f'c{n}-{k}', 'title': f'{TITLES[n - 1]} {k}'} for k in range(1, size + 1)]
    execute(root, {'op': 'curriculum.chapter.save', 'chapter_id': f'ch{n}', 'concepts': concepts})
    route += [c['id'] for c in concepts]

for i, cid in enumerate(route[:41]):
    execute(root, {'op': 'mainline.enter', 'concept_id': cid, 'goal': 'Study', 'next_step': 'Read', 'request_id': f'enter-{i}'})
    if i == 40:
        break
    turn = f'lesson-{i}'
    execute(root, {'op': 'stream.start', 'id': turn, 'concept_id': cid, 'prompt': 'Teach', 'channel': 'mainline'})
    execute(root, {'op': 'stream.event', 'id': turn, 'attempt': 1, 'sequence': 1, 'kind': 'final', 'text': '## Lesson\n\nA short lesson.'})
    execute(root, {'op': 'stream.event', 'id': turn, 'attempt': 1, 'sequence': 2, 'kind': 'complete'})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        text = '{"questions": []}' if 'Practice only' in prompt else '## Lesson\n\nA short lesson.'
        if 'This reply teaches step' in prompt:
            text += '\n<lesson-step>{"remaining": []}</lesson-step>'
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=int(sys.argv[1]) if len(sys.argv) > 1 else 0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'),
          on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
