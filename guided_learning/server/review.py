"""Spaced review in the app (ADR 0008): the schedule, starting a review of a section, and "Not now"."""
import time

from ..store import OperationError


class Review:
    """Review questions are practice tasks with origin `review`; answering one uses the ordinary exercise flow."""

    def __init__(self, host):
        self.host = host
        self.clock = time.time  # tests move the clock instead of waiting days

    def schedule(self):
        return self.host.operation({'op': 'review.schedule', 'now': self.clock()})

    def state(self, practice=None):
        """The schedule with the review questions and the requests generating them, which the section pages leave out."""
        practice = practice or self.host.practice.state()
        return {**self.schedule(),
                'tasks': [t for t in practice['tasks'] if t['origin'] == 'review'],
                'jobs': [j for j in practice['jobs'] if j.get('purpose') == 'review']}

    def start(self, concept_id):
        """Ask the teacher for one fresh retrieval question for a due section, or return the one already waiting."""
        with self.host.lock:
            entry = next((s for s in self.schedule()['due'] if s['concept_id'] == concept_id), None)
            if entry is None:
                raise OperationError('not_due', 'This section is not due for review today')
            if entry['task_id']:
                return {'task_id': entry['task_id']}
            return self.host.practice._launch(concept_id, 'generate', purpose='review')

    def postpone(self, concept_id):
        result = self.host.operation({'op': 'review.postpone', 'concept_id': concept_id, 'now': self.clock()})
        self.host.changed()
        return result
