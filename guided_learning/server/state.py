"""The interface's copy of a course: `/api/state`, projected to the fields the web interface reads (issue #62).

Domain operations keep every field; only this HTTP view leaves out build-time audit fields, frozen prompt snapshots and
text no view shows, so the state stays small on large courses.
"""
import hashlib
import json

from ..streaming import PREPARED_STEP

# Channels whose text a view shows: lessons and side-question answers. Other turns only report their status.
SHOWN = ('mainline', 'sidequestion')
REF = ('source_id', 'revision', 'unit_id')
CONCEPT = ('id', 'title', 'prerequisites', 'objective', 'goal')
COVERAGE = REF + ('concept_ids', 'disposition', 'verification')
JOB = ('id', 'concept_id', 'status', 'reason', 'created_at')
SOURCE = ('id', 'path', 'revision', 'status', 'converted_from')
INTERACTION = ('id', 'role', 'text', 'concept_id')


def _pick(item, keys):
    return {k: item[k] for k in keys if k in item}


def public_turn(summary):
    """A turn summary (`stream.summaries`) as the interface keeps it: `text` is the streamed text, and the final text
    once complete."""
    summary = {k: v for k, v in summary.items() if k not in ('final_text', 'metrics', 'prompt')}
    if summary['channel'] not in SHOWN:
        summary.update(text='', attempts=[], source_refs=[])
    return summary


def _exercise(exercise):
    projected = _pick(exercise, REF + ('question', 'part_of'))
    if 'other_parts' in exercise:
        projected['other_parts'] = [_pick(p, ('question', 'concept_id')) for p in exercise['other_parts']]
    return projected


def _concept(concept):
    projected = _pick(concept, CONCEPT)
    if 'links' in concept:
        projected['links'] = [_pick(r, REF) for r in concept['links']]
    if 'exercises' in concept:
        projected['exercises'] = [_exercise(e) for e in concept['exercises']]
    return projected


def curriculum(model):
    """The route, chapters and what views read of each section, with a version of the whole plan, which the section
    preview reads."""
    return {'version': hashlib.sha1(json.dumps(model, ensure_ascii=False).encode()).hexdigest(),
            'route': model['route'], 'chapters': model['chapters'],
            'concepts': [_concept(c) for c in model['concepts']],
            'coverage': [_pick(c, COVERAGE) for c in model.get('coverage', [])]}


def public_question(branch):
    selected = branch.get('selected_lecture')
    return {**branch, 'selected_lecture': {'id': selected['id']} if selected else None}


def _course(host):
    status = host.operation({'op': 'course.status'})
    return {'course': status['course'], 'position': status['position'], 'sources': [_pick(s, SOURCE) for s in status['sources']]}


def _practice(host):
    practice = host.practice.state()
    # Review questions and their requests live on the review page, not among a section's exercises (ADR 0008).
    # Chapter recaps and quiz questions carry chapter_id; the chapter page lists them, section views leave them out.
    # Replaced exercises are kept for the record only (ADR 0011).
    return {'practice': {'tasks': [t for t in practice['tasks'] if t['origin'] != 'review' and t['status'] != 'replaced'],
                         'jobs': [j for j in practice['jobs'] if j.get('purpose') != 'review']},
            'review': host.review.state(practice)}


def _preparation(host):
    view = host.operation({'op': 'preparation.view', 'brief': True})
    return {'jobs': [_pick(j, JOB) for j in view['jobs']], 'next_concept_id': view['next_concept_id']}


def _session(host):
    session = host.operation({'op': 'session.resume', 'recent_limit': 20})
    return {'recent_interactions': [_pick(i, INTERACTION) for i in session['recent_interactions']]}


# Each part is one or more top-level keys of the state; the interface reloads the parts a `changed` scope names alone.
PARTS = {
    'course': _course,
    'preferences': lambda host: host.operation({'op': 'preferences.view'}),
    'curriculum': lambda host: {'curriculum': curriculum(host.operation({'op': 'curriculum.view'}))},
    'session': lambda host: {'session': _session(host)},
    'deferred_explanations': lambda host: host.operation({'op': 'deferred.list'}),
    # A prepared step stays hidden until Continue reveals it.
    'turns': lambda host: {'turns': [public_turn(t) for t in host.operation({'op': 'stream.summaries'})['turns']
                                     if t['channel'] != PREPARED_STEP]},
    'questions': lambda host: {'questions': [public_question(b) for b in host.questions.list()]},
    'practice': _practice,
    'preparation': lambda host: {'preparation': _preparation(host)},
    'settings': lambda host: {'settings': host.settings.public()},
    'lessons': lambda host: host.operation({'op': 'lesson.list'}),
    'annotations': lambda host: host.operation({'op': 'annotations.list'}),
    'memory': lambda host: {'memory': host.operation({'op': 'memory.view'})['entries']},
    'skipped': lambda host: {'skipped': host.practice.skipped()},
    'builds': lambda host: {'builds': host.builds.state()},
}
# Parts a `changed` event may reload without the rest of the state.
ALONE = ('preparation', 'settings', 'builds', 'memory')


def build(host, parts=None):
    state = {}
    for name in parts or PARTS:
        state.update(PARTS[name](host))
    return state
