"""Per-user Codex teacher settings, stored outside every course workspace."""
import json
import os
import threading
from pathlib import Path

from ..codex import CodexRunner
from ..store import OperationError

EFFORTS = ('minimal', 'low', 'medium', 'high')


def default_path():
    if os.environ.get('GUIDED_LEARNING_CONFIG'):
        return Path(os.environ['GUIDED_LEARNING_CONFIG'])
    if os.name == 'nt' and os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'guided-learning' / 'settings.json'
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'guided-learning' / 'settings.json'


def _clean(model, effort):
    model, effort = str(model or '').strip(), str(effort or 'medium').strip()
    if effort not in EFFORTS:
        raise OperationError('invalid_settings', 'Reasoning effort must be minimal, low, medium or high')
    return {'model': model, 'effort': effort}


class TeacherSettings:
    """The Codex model and reasoning effort; command-line values apply to one run without being saved."""

    def __init__(self, path=None, override=None):
        self.path = Path(path) if path else default_path()
        self.lock = threading.Lock()
        self.override = {k: v for k, v in (override or {}).items() if v}
        if self.override:
            _clean(self.override.get('model'), self.override.get('effort'))

    def _saved(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return _clean('', 'medium')
        except (OSError, ValueError) as exc:
            raise OperationError('invalid_settings', f'Could not read teacher settings at {self.path}') from exc
        return _clean(data.get('model'), data.get('effort'))

    def current(self):
        with self.lock:
            return {**self._saved(), **self.override}

    def public(self):
        return {**self.current(), 'overridden': bool(self.override), 'path': str(self.path)}

    def save(self, model, effort):
        data = _clean(model, effort)
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
            os.replace(temporary, self.path)
            self.override = {}
        return self.public()

    def runner(self):
        settings = self.current()
        return CodexRunner(model=settings['model'] or None, effort=settings['effort'])
