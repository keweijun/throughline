"""Review in the app: the review sets written before drill sessions (ADR 0014, ADR 0025), kept to read and answer,
recall answers, and the warm-ups on offer. New review questions come from drill sessions (`drills.py`)."""
import time


class Review:
    def __init__(self, host):
        self.host = host
        self.clock = time.time  # tests move the clock instead of waiting days

    def operation(self, request):
        return self.host.operation(request)

    def state(self, practice=None):
        """Earlier sets (a prepared one that was never asked for stays hidden), every review question, drill sessions'
        included, the warm-ups on offer and the sections a review may cover."""
        practice = practice or self.host.practice.state()
        listed = self.operation({'op': 'review.sets'})['sets']
        hidden = {s['id'] for s in listed if s.get('prepared')}
        offers = self.operation({'op': 'review.warm_ups', 'now': self.clock()})
        return {'sets': [s for s in listed if s['id'] not in hidden],
                'tasks': [t for t in practice['tasks'] if t['origin'] == 'review' and t.get('set_id') not in hidden],
                'jobs': [j for j in practice['jobs'] if j.get('purpose') == 'review' and j.get('set_id') not in hidden],
                'reviewable': offers['reviewable'], 'sections': offers['sections'], 'warm_ups': offers['warm_ups']}

    def answer(self, task_id, choice):
        result = self.operation({'op': 'review.answer', 'task_id': task_id, 'choice': choice})
        self.host.changed()
        return result

    def dismiss_warm_up(self, concept_id):
        result = self.operation({'op': 'review.dismiss_warm_up', 'concept_id': concept_id})
        self.host.changed()
        return result
