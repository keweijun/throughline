"""Review on request in the app (ADR 0014): asking for a review set, the prepared Review for me set, recall answers and
warm-ups. A set's questions are written by a practice job with purpose review; written answers use the exercise flow."""
import time
import uuid

from ..store import OperationError


class Review:
    def __init__(self, host):
        self.host = host
        self.clock = time.time  # tests move the clock instead of waiting days
        self.ahead = True  # write the prepared set when idle; tests that count requests turn it off

    def operation(self, request):
        return self.host.operation(request)

    def state(self, practice=None):
        """Sets (a prepared one stays hidden until asked for), their questions and the requests writing them, the warm-ups
        on offer and how many sections can be reviewed."""
        practice = practice or self.host.practice.state()
        listed = self.operation({'op': 'review.sets'})['sets']
        hidden = {s['id'] for s in listed if s.get('prepared')}
        return {'sets': [s for s in listed if s['id'] not in hidden],
                'tasks': [t for t in practice['tasks'] if t['origin'] == 'review' and t.get('set_id') not in hidden],
                'jobs': [j for j in practice['jobs'] if j.get('purpose') == 'review' and j.get('set_id') not in hidden],
                'reviewable': len(self.operation({'op': 'review.context', 'now': self.clock()})['sections']),
                'warm_ups': self.operation({'op': 'review.warm_ups', 'now': self.clock()})['warm_ups']}

    def _prepared(self):
        """The prepared set and whether its questions are still usable: written, or being written."""
        value = next((s for s in self.operation({'op': 'review.sets'})['sets'] if s.get('prepared')), None)
        if not value:
            return None, False
        job = next((j for j in self.host.practice.state()['jobs'] if j.get('set_id') == value['id']), None)
        turn = next((t for t in self.host.brief_turns() if job and t['id'] == job['id']), None)
        usable = bool(job) and not job.get('error') and (job.get('processed') or (turn and turn['status'] == 'running'))
        return value, usable

    def ask(self, request=None, scope=None, warm_up_for=None):
        """Ask for a review set. Review for me (nothing given) takes the prepared set when it is usable; a request, a scope
        or a warm-up always writes a new set."""
        with self.host.lock:
            kind = 'warm_up' if warm_up_for else 'request' if (request or '').strip() or scope else 'for_me'
            if kind == 'for_me':
                prepared, usable = self._prepared()
                if prepared:
                    taken = self.operation({'op': 'review.take_prepared', 'id': prepared['id']})['set']
                    if usable:
                        self.host.changed()
                        return {'set': taken}
                    self.operation({'op': 'review.close', 'id': taken['id']})
            created = self.operation({'op': 'review.create', 'id': 'review-' + str(uuid.uuid4()), 'kind': kind,
                                      **({'request': request} if request else {}), **({'scope': scope} if scope else {}),
                                      **({'concept_id': warm_up_for} if warm_up_for else {})})
            return {'set': created['set'], **self._write(created)}

    def _write(self, created):
        """Start the practice job writing a set's questions, anchored to a section it may test (a warm-up to its own
        section, whose lesson comes next)."""
        anchor = created['set'].get('concept_id') or created['sections'][-1]
        return self.host.practice._launch(anchor, 'generate', purpose='review', request={'set_id': created['set']['id']})

    def prepare(self):
        """Write one Review for me set in the background when the host is idle and none is waiting (ADR 0014), in a
        course where the learner has asked for a review before, so no teacher turns go to a learner who never reviews.
        A prepared set that failed is replaced only when the learner asks, so a failing teacher is not retried in a loop."""
        with self.host.lock:
            if self.host.closing or any(t['status'] == 'running' for t in self.host.brief_turns()):
                return None
            sets = self.operation({'op': 'review.sets'})['sets']
            if any(s.get('prepared') for s in sets) or not any(s['kind'] in ('for_me', 'request') for s in sets):
                return None
            try:
                created = self.operation({'op': 'review.create', 'id': 'review-' + str(uuid.uuid4()), 'kind': 'for_me', 'prepared': True})
            except OperationError:
                return None  # nothing studied yet
            return self._write(created)

    def close(self, set_id):
        result = self.operation({'op': 'review.close', 'id': set_id})
        self.host.changed()
        return result

    def answer(self, task_id, choice):
        result = self.operation({'op': 'review.answer', 'task_id': task_id, 'choice': choice})
        self.host.changed()
        return result

    def dismiss_warm_up(self, concept_id):
        result = self.operation({'op': 'review.dismiss_warm_up', 'concept_id': concept_id})
        self.host.changed()
        return result
