"""Streaming runner for any server that implements the OpenAI chat completions API."""
import json
import threading

import httpx


class ProviderError(RuntimeError):
    pass


def _error_message(response):
    try:
        body = json.loads(response.read() or b'{}')
        detail = body.get('error', body)
        if isinstance(detail, dict):
            detail = detail.get('message') or json.dumps(detail)
    except (ValueError, httpx.HTTPError):
        detail = ''
    return f'Provider returned HTTP {response.status_code}' + (f': {str(detail)[:300]}' if detail else '')


class OpenAICompatibleRunner:
    def __init__(self, base_url, model, api_key=None, effort=None, timeout=600, transport=None):
        self.base_url = base_url.rstrip('/')
        self.model, self.api_key, self.effort, self.timeout = model, api_key, effort, timeout
        self.transport = transport

    def _client(self, timeout):
        headers = {'Accept': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout, transport=self.transport)

    def list_models(self):
        with self._client(15) as client:
            response = client.get('/models')
            if response.status_code >= 400:
                raise ProviderError(_error_message(response))
            data = response.json().get('data', [])
        return sorted(item['id'] for item in data if isinstance(item, dict) and item.get('id'))

    def run(self, prompt, cwd, emit, cancel):
        if not self.model:
            raise ProviderError('Choose a model for this provider in Model settings')
        body = {'model': self.model, 'stream': True, 'messages': [{'role': 'user', 'content': prompt}]}
        if self.effort:
            body['reasoning_effort'] = self.effort
        text = []
        finished = threading.Event()
        timeout = httpx.Timeout(self.timeout, connect=15)
        with self._client(timeout) as client:
            # Closing the client from another thread unblocks a read waiting on a slow model.
            def watch():
                while not finished.wait(.1):
                    if cancel.is_set():
                        client.close()
                        return
            threading.Thread(target=watch, daemon=True).start()
            try:
                with client.stream('POST', '/chat/completions', json=body) as response:
                    if response.status_code >= 400:
                        raise ProviderError(_error_message(response))
                    for line in response.iter_lines():
                        if cancel.is_set():
                            return
                        if not line.startswith('data:'):
                            continue
                        payload = line[5:].strip()
                        if payload == '[DONE]':
                            break
                        try:
                            chunk = json.loads(payload)
                        except ValueError:
                            continue
                        if chunk.get('error'):
                            raise ProviderError(str(chunk['error'].get('message', chunk['error']))[:300])
                        for choice in chunk.get('choices') or []:
                            delta = (choice.get('delta') or {}).get('content')
                            if delta:
                                text.append(delta)
                                emit({'kind': 'delta', 'text': delta})
            except (httpx.HTTPError, RuntimeError) as exc:
                if cancel.is_set():
                    return
                if isinstance(exc, ProviderError):
                    raise
                raise ProviderError(f'Could not reach the provider: {exc}') from exc
            finally:
                finished.set()
        if cancel.is_set():
            return
        if not ''.join(text).strip():
            raise ProviderError('Model finished without any reply text')
        emit({'kind': 'final', 'text': ''.join(text)})
        emit({'kind': 'complete'})
