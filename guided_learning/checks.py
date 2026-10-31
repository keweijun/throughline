"""What Throughline needs from outside itself, checked the same way by `guided-learning doctor` and the library (ADR 0017)."""
import subprocess

from . import codex


def run(command, timeout=15):
    return subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                          stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def result(check, ok, detail=''):
    """One check's outcome. `label` and `fix` are English for the command line; the interface words them by `id`."""
    return {'id': check, 'ok': ok, 'label': LABELS[check], 'detail': detail, 'fix': '' if ok else FIXES[check]}


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


def codex_signed_in(context):
    """`codex login status` exits 0 when signed in and 1 when not; anything else is not an answer, so nothing is shown."""
    if not context.get('codex'):
        return None
    try:
        status = context['run']([context['codex'], 'login', 'status'])
    except (OSError, subprocess.SubprocessError):
        return None
    if status.returncode not in (0, 1):
        return None
    return result('signed_in', status.returncode == 0, (status.stdout or status.stderr).strip())


LABELS = {'codex': 'Codex', 'signed_in': 'Signed in to Codex'}
FIXES = {'codex': 'Install Codex (the desktop app or the CLI: https://learn.chatgpt.com/docs/codex/cli), or set CODEX_CLI_PATH',
         'signed_in': 'Sign in to Codex: run `codex login`'}
# The checks the library shows when one fails. Studio (#107) appends its check that Codex has the App Server
# methods it needs, with its label and fix in LABELS and FIXES. A check returns None when it cannot tell.
CODEX_CHECKS = [codex_found, codex_signed_in]


def codex_checks(checks=None, runner=run):
    context = {'run': runner}
    found = (check(context) for check in (CODEX_CHECKS if checks is None else checks))
    return [outcome for outcome in found if outcome]
