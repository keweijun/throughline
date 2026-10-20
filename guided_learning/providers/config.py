"""Per-user model provider settings, stored outside every course workspace."""
import json
import os
import re
import threading
from pathlib import Path

from ..store import OperationError
from .codex import CodexRunner
from .openai_compat import OpenAICompatibleRunner

KINDS = ('codex', 'openai')
EFFORTS = ('minimal', 'low', 'medium', 'high')
DEFAULT = {'active': 'codex', 'providers': [{'id': 'codex', 'kind': 'codex', 'label': 'Local Codex CLI', 'model': '', 'effort': 'medium'}]}


def default_path():
    if os.environ.get('GUIDED_LEARNING_CONFIG'):
        return Path(os.environ['GUIDED_LEARNING_CONFIG'])
    if os.name == 'nt' and os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'guided-learning' / 'providers.json'
    base = os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config'
    return Path(base) / 'guided-learning' / 'providers.json'


def _clean(provider):
    identifier = str(provider.get('id', '')).strip()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', identifier):
        raise OperationError('invalid_provider', 'Provider ID must be lowercase letters, digits or hyphens')
    kind = provider.get('kind')
    if kind not in KINDS:
        raise OperationError('invalid_provider', 'Provider kind must be codex or openai')
    effort = provider.get('effort') or ''
    if effort and effort not in EFFORTS:
        raise OperationError('invalid_provider', 'Reasoning effort must be minimal, low, medium or high')
    clean = {'id': identifier, 'kind': kind, 'label': str(provider.get('label') or identifier).strip()[:80],
             'model': str(provider.get('model') or '').strip(), 'effort': effort}
    if kind == 'openai':
        base_url = str(provider.get('base_url') or '').strip().rstrip('/')
        if not re.match(r'https?://', base_url):
            raise OperationError('invalid_provider', 'Base URL must start with http:// or https://')
        clean['base_url'] = base_url
        env = str(provider.get('api_key_env') or '').strip()
        if env and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', env):
            raise OperationError('invalid_provider', 'API key variable must be an environment variable name')
        clean['api_key_env'] = env
        if provider.get('api_key'):
            clean['api_key'] = str(provider['api_key'])
    return clean


class ProviderSettings:
    """Reads and writes provider settings; API keys never leave this object except to runners."""

    def __init__(self, path=None, override=None):
        self.path = Path(path) if path else default_path()
        self.lock = threading.Lock()
        self.override = override or {}

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return json.loads(json.dumps(DEFAULT))
        except (OSError, ValueError) as exc:
            raise OperationError('invalid_settings', f'Could not read provider settings at {self.path}') from exc
        providers = [_clean(p) for p in data.get('providers', [])] or DEFAULT['providers']
        active = data.get('active')
        if not any(p['id'] == active for p in providers):
            active = providers[0]['id']
        return {'active': active, 'providers': providers}

    def _save(self, data):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        # Created owner-only, so an API key is never readable by others, even briefly.
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            file.write(json.dumps(data, indent=2, ensure_ascii=False))
        os.replace(temporary, self.path)

    def _find(self, data, identifier):
        provider = next((p for p in data['providers'] if p['id'] == identifier), None)
        if provider is None:
            raise OperationError('unknown_provider', f'Unknown provider {identifier}')
        return provider

    def active(self):
        with self.lock:
            data = self._load()
        provider = dict(self._find(data, self.override.get('provider') or data['active']))
        for key in ('model', 'effort'):
            if self.override.get(key):
                provider[key] = self.override[key]
        return provider

    def public(self):
        with self.lock:
            data = self._load()
        active = self.active()
        providers = []
        for provider in data['providers']:
            visible = {k: v for k, v in provider.items() if k != 'api_key'}
            if provider['kind'] == 'openai':
                visible['has_api_key'] = bool(provider.get('api_key') or os.environ.get(provider.get('api_key_env') or ''))
            providers.append(visible)
        return {'active': active['id'], 'active_model': active['model'], 'providers': providers,
                'overridden': bool(self.override), 'path': str(self.path)}

    def upsert(self, provider):
        with self.lock:
            data = self._load()
            existing = next((p for p in data['providers'] if p['id'] == provider.get('id')), None)
            if existing and 'api_key' not in provider and existing.get('api_key'):
                provider = {**provider, 'api_key': existing['api_key']}
            clean = _clean(provider)
            data['providers'] = [p for p in data['providers'] if p['id'] != clean['id']] + [clean]
            self._save(data)
        return self.public()

    def remove(self, identifier):
        with self.lock:
            data = self._load()
            self._find(data, identifier)
            if len(data['providers']) == 1:
                raise OperationError('invalid_provider', 'Keep at least one provider')
            if data['active'] == identifier:
                raise OperationError('provider_in_use', 'Choose another provider before removing the one in use')
            data['providers'] = [p for p in data['providers'] if p['id'] != identifier]
            self._save(data)
        return self.public()

    def activate(self, identifier, model=None):
        with self.lock:
            data = self._load()
            provider = self._find(data, identifier)
            if model is not None:
                provider['model'] = model.strip()
            data['active'] = identifier
            self._save(data)
            self.override = {}
        return self.public()

    def draft_runner(self, provider):
        """A runner for unsaved settings; a saved key is reused only for the same server."""
        with self.lock:
            existing = next((p for p in self._load()['providers'] if p['id'] == provider.get('id')), {})
        same_server = existing.get('base_url') == str(provider.get('base_url') or '').strip().rstrip('/')
        if not provider.get('api_key') and existing.get('api_key') and same_server:
            provider = {**provider, 'api_key': existing['api_key']}
        return self._build(_clean(provider))

    def runner(self):
        return self._build(self.active())

    def _build(self, provider):
        if provider['kind'] == 'codex':
            return CodexRunner(model=provider['model'] or None, effort=provider['effort'] or 'medium')
        key = provider.get('api_key') or os.environ.get(provider.get('api_key_env') or '') or None
        return OpenAICompatibleRunner(provider['base_url'], provider['model'], api_key=key, effort=provider['effort'] or None)
