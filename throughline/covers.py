"""A course's cover on its library card (ADR 0027).

The cover is the subject's short name over a pattern of thin lines. Codex chooses both, since it has read the
materials: the name a student would use for the subject, and the pattern that suits it. The app draws the pattern,
so a cover is two short strings and every cover is in the same hand.
"""
from .store import OperationError


# id -> what Codex reads when choosing: what the pattern looks like and the subjects it suits. The app draws each one
# (`web/src/lib/covers.ts`) and draws `contours` for an id it does not know, so removing one never breaks a card.
PATTERNS = {
    'contours': {'looks': 'closed curves nested like a contour map',
                 'subjects': 'thermodynamics, earth sciences, geography, optimisation, anything with surfaces and levels'},
    'waves': {'looks': 'stacked oscillating traces',
              'subjects': 'signals, acoustics, optics, spectroscopy, analytical chemistry, oscillations'},
    'lattice': {'looks': 'a mesh of linked six-sided cells',
                'subjects': 'chemistry, materials science, crystallography, molecular biology, networks'},
    'grid': {'looks': 'a ruled plane bent by a map',
             'subjects': 'linear algebra, calculus, geometry, complex analysis, relativity'},
    'orbits': {'looks': 'nested ellipses, each turned a little further',
               'subjects': 'mechanics, astronomy, atomic and quantum physics, physical chemistry'},
    'field': {'looks': 'lines flowing from one pole to another',
              'subjects': 'electromagnetism, fluid dynamics, differential equations, vector calculus'},
    'branches': {'looks': 'a tree forking level by level',
                 'subjects': 'algorithms, data structures, programming, logic, evolution, linguistics'},
    'scatter': {'looks': 'a cloud of points around a trend line',
                'subjects': 'statistics, probability, data science, economics, psychology, social sciences'},
    'ruled': {'looks': 'lines of writing on a page, one passage marked',
              'subjects': 'history, literature, law, philosophy, languages, anything read rather than computed'},
}

# The name is set large on a small card.
NAME_LENGTH = 16


def cover(store):
    """The course's cover, or None for a course that has none yet."""
    return store.get('course', 'cover')


def listing(store, request):
    return {'patterns': [{'id': name, **item} for name, item in PATTERNS.items()], 'cover': cover(store)}


def save(store, request):
    """Set the course's cover, replacing any earlier one."""
    name, pattern = request.get('name'), request.get('pattern')
    if not isinstance(name, str) or not name.strip() or '\n' in name.strip():
        raise OperationError('invalid_cover', 'name must be a short name for the subject, on one line')
    name = ' '.join(name.split())
    if len(name) > NAME_LENGTH:
        raise OperationError('invalid_cover', f'name must be at most {NAME_LENGTH} characters; it is set large on a small card')
    if pattern not in PATTERNS:
        raise OperationError('unknown_pattern', f'Unknown pattern: {pattern!r}; cover.list shows the patterns')
    store.put('course', 'cover', {'name': name, 'pattern': pattern})
    return {'cover': cover(store)}


OPERATIONS = {'cover.list': listing, 'cover.save': save}
