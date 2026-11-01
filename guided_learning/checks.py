"""What Throughline needs from outside itself, checked the same way by `guided-learning doctor` and the library (ADR 0017).

Two kinds of check. Cheap ones (CODEX_CHECKS) run every time they are asked. The probe, `codex_answers`, sends Codex one
tiny turn on a small model and waits for the reply: it costs a little usage and takes seconds, so the library runs it
at most once per host and keeps the result. It replaces asking `codex login status`, which says "Not logged in" to
learners who use an API key and whose Codex answers fine; what matters is whether Codex can answer.
"""
import subprocess
import tempfile
import threading
import time

from . import codex
from .store import OperationError

PROBE = 'Reply with the single word OK.'


def run(command, timeout=15):
    return subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                          stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def result(check, ok, detail='', **extra):
    """One check's outcome. `label` and `fix` are English for the command line; the interface words them by `id`."""
    return {'id': check, 'ok': ok, 'label': LABELS[check], 'detail': detail, 'fix': '' if ok else FIXES[check], **extra}


def codex_found(context):
    path = codex.find_codex()
    if not path:
        return result('codex', False)
    context['codex'] = path
    try:
        found = context['run']([path, '--version'])
    except (OSError, subprocess.SubprocessError):
        return result('codex', False, path)
    return result('codex', found.returncode == 0, f'{found.stdout.strip()} ({path})' if found.returncode == 0 else path)


def probe_model(settings=None, models=codex.list_models):
    """The learner's small model if set; else a small "luna" model this account offers; else the teacher's or Codex's default."""
    try:
        current = settings.current() if settings else {}
    except OperationError:
        current = {}  # unreadable settings: still probe, with a model Codex offers
    if current.get('small_model'):
        return current['small_model']
    try:
        offered = [m['id'] for m in models()]
    except (OSError, RuntimeError):
        offered = []
    return next((m for m in offered if 'luna' in m), None) or current.get('model') or None


def codex_answers(model=None, runner=codex.CodexRunner, timeout=60, idle_timeout=30):
    """Send one tiny turn and wait for a reply. `model` None means Codex's default; the result names what was used."""
    replies = []
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory() as cwd:
            runner(model=model, effort='low', timeout=timeout, idle_timeout=idle_timeout).run(
                PROBE, cwd, lambda event: replies.append(event), threading.Event())
        error = '' if any(e.get('kind') == 'final' for e in replies) else 'Codex finished without a reply'
    except Exception as exc:  # whatever Codex said went wrong is the useful part
        error = str(exc) or exc.__class__.__name__
    seconds = round(time.monotonic() - started, 1)
    error = ' '.join(error.split())
    if len(error) > 300:
        error = error[:297] + '...'
    return result('answers', not error, error, model=model or 'Codex default', seconds=seconds)


LABELS = {'codex': 'Codex', 'answers': 'Codex answers'}
FIXES = {'codex': 'Install Codex (the desktop app or the CLI: https://learn.chatgpt.com/docs/codex/cli), or set CODEX_CLI_PATH',
         'answers': 'Check that `codex` works in a terminal (signed in, or with an API key).'}
# The cheap checks, run whenever asked. Studio (#107) appends its check that Codex has the App Server methods it needs,
# with its label and fix in LABELS and FIXES. A check returns None when it cannot tell.
CODEX_CHECKS = [codex_found]


def codex_checks(checks=None, runner=run):
    context = {'run': runner}
    found = (check(context) for check in (CODEX_CHECKS if checks is None else checks))
    return [outcome for outcome in found if outcome]


class CodexStatus:
    """What the library shows about Codex. The cheap checks run on every request; the probe runs in the background at
    most once per host, the first time the library asks, and its result, a failure too, is kept until `again()`."""

    def __init__(self, settings=None, cheap=codex_checks, probe=None):
        self.cheap = cheap
        self.probe = probe or (lambda: codex_answers(probe_model(settings)))
        self.lock = threading.Lock()
        self.answer = None
        self.checking = False
        self.started = False

    def _start(self):
        with self.lock:
            if self.checking:
                return
            self.checking = self.started = True
        threading.Thread(target=self._probe, name='codex-probe', daemon=True).start()

    def _probe(self):
        try:
            answer = self.probe()
        except Exception as exc:  # a bug in the probe must not leave the library checking forever
            answer = result('answers', False, f'{exc.__class__.__name__}: {exc}')
        with self.lock:
            self.answer, self.checking = answer, False

    def view(self):
        """Never waits for the probe: while it runs, `checking` is true and the last answer, if any, is kept."""
        found = self.cheap()
        if all(check['ok'] for check in found) and not self.started:
            self._start()
        with self.lock:
            answer = [self.answer] if self.answer and all(check['ok'] for check in found) else []
            return {'checks': found + answer, 'checking': self.checking}

    def again(self):
        if all(check['ok'] for check in self.cheap()):
            self._start()
        return self.view()
