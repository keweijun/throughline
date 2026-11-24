"""Study activity (Settings → Activity): when the learner studied, read from what each course already records.

Nothing new is tracked. Lesson steps, exercise work, side questions and drill messages are stream turns with the time
the learner asked for them; check and recall answers, and notes, carry their own times. What the teacher or background
work did on its own is left out: a step prepared ahead counts from when the learner revealed it, an exercise from when
it was worked on rather than written. A course imported fresh from someone else counts only from its import, and the
sender's notes that came with it not at all. Records from before the app kept times have none and are not shown.

The interface turns the times into days and estimated study time in the learner's own time zone, which only the
browser knows.
"""
import sqlite3
from pathlib import Path

from .library import stamp
from .moving import MOVING

# What a time records; the interface names them. Indexes into this tuple are what `read` returns.
KINDS = ('step', 'answer', 'question', 'note', 'drill')

_TURN = "SELECT {time} FROM documents WHERE namespace = 'streams' AND json_extract(value, '$.channel') = '{channel}'"
QUERIES = (
    # A lesson step the learner was taught; one written ahead joins the lesson when they reveal it.
    ('step', _TURN.format(time="COALESCE(json_extract(value, '$.revealed_at'), json_extract(value, '$.started_at'))", channel='mainline')),
    # Working on an exercise: an answer to assess, a hint, a solution.
    ('answer', _TURN.format(time="json_extract(value, '$.started_at')", channel='practice')),
    ('answer', "SELECT json_extract(s.value, '$.answer.answered_at') FROM documents AS d, json_each(d.value, '$.steps') AS s "
               "WHERE d.namespace = 'lessons'"),
    ('answer', "SELECT json_extract(value, '$.answer.at') FROM documents WHERE namespace = 'practice_tasks'"),
    # A side question and each follow-up are one turn each.
    ('question', _TURN.format(time="json_extract(value, '$.started_at')", channel='sidequestion')),
    ('note', "SELECT json_extract(value, '$.created_at') FROM documents WHERE namespace = 'annotations' "
             "AND json_extract(value, '$.from_sender') IS NULL"),
    ('drill', _TURN.format(time="json_extract(value, '$.started_at')", channel='drill')),
)
IMPORTED = "SELECT json_extract(value, '$.at') FROM documents WHERE namespace = 'course' AND key = 'imported'"

# Each course's times and the database stamp they were read at: most courses have not changed since the last visit.
_read = {}


def read(path):
    """The course's activity as [time, kind index] pairs, oldest first. Reads without locking or migrating."""
    path = Path(path).resolve()
    taken = stamp(path)
    cached = _read.get(path)
    if cached and taken is not None and cached[0] == taken:
        return cached[1]
    events = _events(path)
    _read[path] = (taken, events)
    return events


def _events(path):
    if (path / MOVING).exists():
        return []
    try:
        db = sqlite3.connect((path / 'course.sqlite3').as_uri() + '?mode=ro', uri=True, timeout=1)
    except sqlite3.Error:
        return []
    try:
        row = db.execute(IMPORTED).fetchone()
        since = row[0] if row and isinstance(row[0], (int, float)) else 0
        events = []
        for kind, query in QUERIES:
            try:
                rows = db.execute(query).fetchall()
            except sqlite3.Error:  # a record in an older shape; the rest still count
                continue
            index = KINDS.index(kind)
            events.extend([round(t, 1), index] for (t,) in rows if isinstance(t, (int, float)) and t > since)
    except sqlite3.Error:
        return []
    finally:
        db.close()
    return sorted(events)


def view(courses):
    """Every course's activity, for courses given as library summaries (`name`, `path`, `title`, `archived`)."""
    return {'kinds': list(KINDS),
            'courses': [{'name': c['name'], 'title': c.get('title') or c['name'], 'archived': bool(c.get('archived')),
                         'events': read(c['path'])} for c in courses if not c.get('error')]}
