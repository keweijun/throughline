"""Per-user Codex teacher settings, stored outside every course workspace."""
import json
import os
import threading
from pathlib import Path

from ..codex import CodexRunner, list_models
from ..store import OperationError

# The reasoning efforts Throughline offers, lowest first; each model offers its own subset (`model/list`). Codex's
# `ultra` is left out on purpose.
EFFORTS = ('minimal', 'low', 'medium', 'high', 'xhigh', 'max')


def default_path():
    if os.environ.get('GUIDED_LEARNING_CONFIG'):
        return Path(os.environ['GUIDED_LEARNING_CONFIG'])
    if os.name == 'nt' and os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'guided-learning' / 'settings.json'
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'guided-learning' / 'settings.json'


def _clean(model, effort, small_model='', service_tier='', small_effort=''):
    model, effort = str(model or '').strip(), str(effort or 'medium').strip()
    small_effort = str(small_effort or '').strip()
    if effort not in EFFORTS or small_effort not in ('', *EFFORTS):
        raise OperationError('invalid_settings', f"Reasoning effort must be one of {', '.join(EFFORTS)}")
    return {'model': model, 'small_model': str(small_model or '').strip(), 'effort': effort,
            'small_effort': small_effort, 'service_tier': str(service_tier or '').strip()}


class TeacherSettings:
    """The Codex teacher model, the small model for section preparation and note consolidation, and reasoning effort.

    The service tier (for example Codex's "priority" tier, shown as Fast) applies to teacher turns only.
    Command-line values apply to one run without being saved. An empty model or service tier means the
    Codex default; an empty small model or small effort means the teacher's.
    """

    def __init__(self, path=None, override=None):
        self.path = Path(path) if path else default_path()
        self.lock = threading.Lock()
        self.override = {k: v for k, v in (override or {}).items() if v}
        if self.override:
            _clean(self.override.get('model'), self.override.get('effort'), self.override.get('small_model'),
                   self.override.get('service_tier'), self.override.get('small_effort'))

    def _saved(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return _clean('', 'medium')
        except (OSError, ValueError) as exc:
            raise OperationError('invalid_settings', f'Could not read teacher settings at {self.path}') from exc
        return _clean(data.get('model'), data.get('effort'), data.get('small_model'), data.get('service_tier'),
                      data.get('small_effort'))

    def current(self):
        with self.lock:
            return {**self._saved(), **self.override}

    def public(self):
        return {**self.current(), 'overridden': bool(self.override), 'path': str(self.path)}

    def save(self, model, effort, small_model='', service_tier='', small_effort=''):
        data = _clean(model, effort, small_model, service_tier, small_effort)
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
            os.replace(temporary, self.path)
            self.override = {}
        return self.public()

    def runner(self, small=False):
        settings = self.current()
        model = (small and settings['small_model']) or settings['model']
        effort = (small and settings['small_effort']) or settings['effort']
        tier = None if small else settings['service_tier'] or None
        return CodexRunner(model=model or None, effort=effort, service_tier=tier)

    def models(self):
        return {'models': list_models()}


class Seen:
    """What this learner has dismissed for good, such as the library's launcher card; saved per user beside the settings."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def _saved(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return [str(item) for item in data.get('seen', [])]
        except (OSError, ValueError, AttributeError, TypeError):
            return []  # unreadable means nothing dismissed yet: the card shows again, which is harmless

    def all(self):
        with self.lock:
            return self._saved()

    def add(self, item):
        with self.lock:
            seen = self._saved()
            if item not in seen:
                seen.append(item)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps({'seen': seen}, indent=2), encoding='utf-8')
                os.replace(temporary, self.path)
            return seen
