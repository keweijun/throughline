"""A course whose lesson uses every teaching widget, a broken diagram and a broken plot (ADR 0013)."""
from pathlib import Path
import tempfile
import time

from guided_learning.api import execute
from guided_learning.server.settings import TeacherSettings
from guided_learning.server import serve

LESSON = r'''Water forms from hydrogen and oxygen: $\ce{2H2 + O2 -> 2H2O}$.

> [!WARNING]
> Amplitudes add before squaring.

> A plain quotation stays a quotation.

```python
def probability(a, b):
    return abs(a + b) ** 2  # interference
```

```mermaid
flowchart LR
  A[Two paths] --> B{Same phase?}
  B -->|yes| C[Bright]
  B -->|no| D[Dark]
```

```mermaid
flowchart LR
  A -->
```

```mermaid
---
config:
  layout: elk
---
flowchart LR
  P[Elk asked] --> Q[Dagre drew]
```

```plot
x: -3, 3
f: x^2 - 1
f: 2*sin(x)
point: 1, 0, root
```

```plot
f: y^2
```
'''

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
execute(root, {'op': 'course.init', 'title': 'Widgets'})
execute(root, {'op': 'curriculum.save', 'concepts': [{'id': 'wave', 'title': 'Wave superposition'}], 'route': ['wave'], 'coverage': []})
execute(root, {'op': 'widgets.save', 'ids': ['plot', 'chemistry']})


class Runner:
    def run(self, prompt, cwd, emit, cancel):
        # Stream in pieces so a fence is open part of the time, as with a real teacher.
        for start in range(0, len(LESSON), 40):
            emit({'kind': 'delta', 'text': LESSON[start:start + 40]})
            time.sleep(0.01)
        text = LESSON + ('\n<lesson-step>{"remaining": []}</lesson-step>' if 'This reply teaches step' in prompt else '')
        emit({'kind': 'final', 'text': text})
        emit({'kind': 'complete'})


try:
    serve(root, port=0, runner=Runner(), settings=TeacherSettings(root / 'settings.json'), on_ready=lambda port: print(port, flush=True))
finally:
    scratch.cleanup()
