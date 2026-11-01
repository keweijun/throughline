"""Teaching widget add-ons a course selects (ADR 0013).

Basic widgets (LaTeX, highlighted code, callouts, Mermaid diagrams) are always available and described in the teacher
instructions. Add-ons serve particular subjects: Codex selects a course's add-ons while building it, and only their guides
enter the teacher's instructions. The app renders every add-on in the library whether or not a course selects it, so
removing one never breaks lessons already written with it.
"""
from .store import OperationError


# id -> what Codex reads when choosing (`summary`, `subjects`) and what the teacher reads once selected (`guide`).
LIBRARY = {
    'plot': {
        'summary': 'Graphs of functions of one variable, with optional marked points',
        'subjects': 'calculus, algebra, physics, economics, signal processing, statistics',
        'guide': '''Function plots: draw the graph of one or more functions of x in a fenced code block with the language "plot". Each line is `key: value`; give one or more `f:` lines, optional `x:` and `y:` ranges and optional `point:` lines:
```plot
x: -3, 3
y: -2, 6
f: x^2 - 1
f: 2*sin(x)
point: 1, 0, root
```
Expressions use x, numbers, + - * / ^, parentheses, pi, e and sin, cos, tan, asin, acos, atan, sinh, cosh, tanh, exp, ln, log10, sqrt, abs, floor, ceil and sign; write multiplication with *. Use a plot when the shape of a graph explains the idea, not for values the learner should compute.''',
    },
    'chemistry': {
        'summary': 'Chemical formulas, equations and physical units (mhchem)',
        'subjects': 'chemistry, biochemistry, materials science',
        'guide': r'''Chemistry: inside LaTeX math, write chemical formulas and equations with \ce{...} and quantities with units with \pu{...}, for example $\ce{2H2 + O2 -> 2H2O}$, $\ce{SO4^2-}$, $\ce{A <=> B}$ and $\pu{25 kJ mol-1}$.''',
    },
    'python': {
        'summary': 'Python code the learner runs and changes in the lesson or completes in an exercise',
        'subjects': 'programming, numerical methods, data analysis, statistics, scientific computing, algorithms',
        'guide': '''Runnable Python: put code the learner should run, change or complete in a fenced code block with the language "python-run"; the app shows it as an editable cell with Run, and in an exercise the learner can add their code and its output to their answer. Use a plain ```python block for code that is only read.
```python-run
import numpy as np
xs = np.linspace(0, 1, 5)
print(xs ** 2)
```
The code runs in the learner's browser (Pyodide, Python 3.14) with the standard library and packages such as numpy, scipy, sympy and pandas, loaded from its imports. Output is text: print what matters; there are no plots, no input(), no files and no network. Keep a cell short and self-contained: cells do not share variables, and each run starts fresh. In an exercise, give starter code that marks what the learner completes with a comment such as `# your code here`, and assess the code and output they submit like any answer.''',
    },
}


def selected(store):
    """The course's add-on ids in library order; a course saved before add-ons existed has none."""
    chosen = set((store.get('course', 'widgets') or {}).get('ids', []))
    return [name for name in LIBRARY if name in chosen]


def guides(ids):
    """Teacher instructions for the given add-ons; ids no longer in the library are ignored."""
    return '\n'.join(LIBRARY[name]['guide'] for name in LIBRARY if name in ids)


def listing(store, request):
    return {'library': [{'id': name, 'summary': item['summary'], 'subjects': item['subjects']} for name, item in LIBRARY.items()],
            'selected': selected(store)}


def save(store, request):
    """Replace the course's add-on selection."""
    ids = request.get('ids')
    if not isinstance(ids, list) or any(not isinstance(name, str) for name in ids):
        raise OperationError('invalid_request', 'ids must be a list of add-on ids')
    unknown = [name for name in ids if name not in LIBRARY]
    if unknown:
        raise OperationError('unknown_widget', f'Unknown add-on: {", ".join(unknown)}; widgets.list shows the library')
    store.put('course', 'widgets', {'ids': [name for name in LIBRARY if name in ids]})
    return listing(store, request)


OPERATIONS = {'widgets.list': listing, 'widgets.save': save}
