"""The course library: one per-user directory holding every course workspace."""
import os
import re
from pathlib import Path

from .api import execute
from .store import OperationError

NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')


def data_dir():
    if os.environ.get('GUIDED_LEARNING_HOME'):
        return Path(os.environ['GUIDED_LEARNING_HOME'])
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / 'guided-learning'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'guided-learning'


def default_root():
    return data_dir() / 'courses'


def course_path(root, name):
    if not isinstance(name, str) or not NAME.match(name):
        raise OperationError('invalid_course_name', 'Course names use lowercase letters, digits and hyphens, for example quantum-v1')
    return Path(root).resolve() / name


def is_course(path):
    return (Path(path) / 'course.sqlite3').is_file()


def summary(path):
    """What the library shows for one course; reads through operations, never edits."""
    path = Path(path).resolve()
    status = execute(path, {'op': 'course.status'})
    curriculum = execute(path, {'op': 'curriculum.view'})
    coverage = execute(path, {'op': 'curriculum.coverage'})
    concepts = {c['id']: c for c in curriculum['concepts']}
    current = (status['position'] or {}).get('concept_id')
    return {'name': path.name,
            'path': str(path),
            'title': status['course']['title'],
            'sources': len(status['sources']),
            'concepts': len(curriculum['route']),
            'needs_review': sum(1 for unit in coverage['units'] if unit['disposition'] in ('needs_review', 'unmapped')),
            'current': concepts.get(current, {}).get('title'),
            'updated': (path / 'course.sqlite3').stat().st_mtime}


def list_courses(root):
    root = Path(root)
    if not root.is_dir():
        return []
    courses = []
    for path in sorted(p for p in root.iterdir() if p.is_dir() and is_course(p)):
        try:
            courses.append(summary(path))
        except (OperationError, OSError) as exc:
            courses.append({'name': path.name, 'path': str(path.resolve()), 'error': str(exc)})
    return sorted(courses, key=lambda c: c.get('updated', 0), reverse=True)
