"""Study activity read from what courses already record (Settings → Activity)."""
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from guided_learning import activity
from guided_learning.api import execute
from guided_learning.server import create_app
from guided_learning.server.settings import TeacherSettings
from guided_learning.store import Store

DAY = 86400
T = 1_790_000_000  # some time in 2026


def turn(store, key, channel, started, **extra):
    store.put('streams', key, {'id': key, 'channel': channel, 'concept_id': 'first', 'status': 'completed', 'started_at': started, **extra})


class Activity(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def course(self, name, title):
        execute(self.root / name, {'op': 'course.init', 'title': title})
        return Store(self.root / name)

    def kinds(self, name):
        return [(t, activity.KINDS[k]) for t, k in activity.read(self.root / name)]

    def test_what_the_learner_did_counts_and_what_was_done_for_them_does_not(self):
        store = self.course('waves', 'Waves')
        turn(store, 's1', 'mainline', T)
        # A step written ahead counts when the learner reveals it; one still waiting does not count yet.
        turn(store, 's2', 'mainline', T + 10, revealed_at=T + 600)
        turn(store, 's3', 'prepared_step', T + 20)
        turn(store, 'p1', 'practice', T + 700)
        turn(store, 'q1', 'sidequestion', T + 800)
        turn(store, 'd1', 'drill', T + DAY)
        for channel in ('preparation', 'build', 'consolidation', 'memory', 'key_points', 'chapter_sheet'):
            turn(store, channel, channel, T + 900)
        store.put('lessons', 'l1', {'id': 'l1', 'created_at': T - 5, 'steps': [
            {'turn_id': 's1', 'answer': {'choice': 0, 'correct': True, 'answered_at': T + 300}}, {'turn_id': 's2'}]})
        # An exercise counts when it is answered, not when the teacher wrote it.
        store.put('practice_tasks', 'x1', {'id': 'x1', 'created_at': T - 50, 'answer': {'choice': 1, 'at': T + 2 * DAY}})
        store.put('practice_tasks', 'x2', {'id': 'x2', 'created_at': T - 40})
        store.put('annotations', 'n1', {'id': 'n1', 'kind': 'note', 'created_at': T + 400})
        store.db.commit()
        store.db.close()
        self.assertEqual(self.kinds('waves'), [
            (T, 'step'), (T + 300, 'answer'), (T + 400, 'note'), (T + 600, 'step'), (T + 700, 'answer'),
            (T + 800, 'question'), (T + DAY, 'drill'), (T + 2 * DAY, 'answer')])

    def test_a_course_imported_fresh_counts_from_its_import_without_the_senders_notes(self):
        store = self.course('shared', 'Shared')
        store.put('course', 'imported', {'title': 'Shared', 'level': 'lessons', 'notes': True, 'at': T + 1000})
        turn(store, 'theirs', 'mainline', T)  # the sender's lesson, shared with the course
        turn(store, 'revealed', 'mainline', T, revealed_at=T + 2000)  # taught to this learner after the import
        store.put('annotations', 'theirs', {'id': 'theirs', 'created_at': T + 1500, 'from_sender': True})
        store.put('annotations', 'mine', {'id': 'mine', 'created_at': T + 3000})
        store.db.commit()
        store.db.close()
        self.assertEqual(self.kinds('shared'), [(T + 2000, 'step'), (T + 3000, 'note')])

    def test_records_without_times_or_in_an_older_shape_are_left_out(self):
        store = self.course('old', 'Old')
        store.put('practice_tasks', 'x', {'id': 'x', 'answer': {'choice': 0}})
        store.put('lessons', 'l', {'id': 'l', 'steps': 'not a list'})
        store.put('annotations', 'n', {'id': 'n', 'created_at': 0})
        turn(store, 's', 'mainline', None)
        store.db.commit()
        store.db.close()
        self.assertEqual(self.kinds('old'), [])

    def test_the_host_lists_every_library_course_with_its_activity(self):
        store = self.course('waves', 'Waves')
        turn(store, 's1', 'mainline', T)
        store.db.commit()
        store.db.close()
        self.course('empty', 'Empty').db.close()
        config = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, config, ignore_errors=True)
        app = create_app(port=8765, runner=None, settings=TeacherSettings(config / 's.json'), library_root=self.root)
        with TestClient(app, base_url='http://127.0.0.1:8765') as client:
            view = client.get('/api/activity').json()
        self.assertEqual(view['kinds'], ['step', 'answer', 'question', 'note', 'drill'])
        self.assertEqual(sorted((c['title'], c['events']) for c in view['courses']), [('Empty', []), ('Waves', [[T, 0]])])


if __name__ == '__main__':
    unittest.main()
