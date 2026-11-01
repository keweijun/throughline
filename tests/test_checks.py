"""The checks of what Throughline needs from Codex, run against a fake Codex; nothing here calls a real model."""
import subprocess
import unittest
from unittest import mock

from guided_learning import checks
from guided_learning.store import OperationError


def fake_version(command):
    return subprocess.CompletedProcess(command, 0, 'codex-cli 0.164.0\n', '')


class Settings:
    def __init__(self, values=None, broken=False):
        self.values, self.broken = values or {}, broken

    def current(self):
        if self.broken:
            raise OperationError('invalid_settings', 'unreadable')
        return {'model': '', 'small_model': '', **self.values}


def runner(events=(), error=None, seen=None):
    """A stand-in for CodexRunner that records how it was made and asked."""
    class Runner:
        def __init__(self, **options):
            if seen is not None:
                seen.append(options)

        def run(self, prompt, cwd, emit, cancel):
            if seen is not None:
                seen.append(prompt)
            for event in events:
                emit(event)
            if error:
                raise error
    return Runner


class CodexFound(unittest.TestCase):
    def test_found_with_its_version(self):
        with mock.patch.object(checks.codex, 'find_codex', return_value='/bin/codex'):
            found = checks.codex_checks(runner=fake_version)
        self.assertEqual([(c['id'], c['ok'], c['detail'], c['fix']) for c in found], [('codex', True, 'codex-cli 0.164.0 (/bin/codex)', '')])

    def test_not_found_says_how_to_get_it(self):
        with mock.patch.object(checks.codex, 'find_codex', return_value=None):
            found = checks.codex_checks(runner=fake_version)
        self.assertEqual([(c['id'], c['ok']) for c in found], [('codex', False)])
        self.assertIn('Install Codex', found[0]['fix'])

    def test_a_codex_that_does_not_run_fails(self):
        def broken(command):
            raise FileNotFoundError(command[0])
        with mock.patch.object(checks.codex, 'find_codex', return_value='/missing/codex'):
            found = checks.codex_checks(runner=broken)
        self.assertEqual([(c['id'], c['ok'], c['detail']) for c in found], [('codex', False, '/missing/codex')])

    def test_later_work_can_add_a_check(self):
        extra = lambda context: checks.result('codex', context.get('codex') == '/bin/codex')
        with mock.patch.object(checks.codex, 'find_codex', return_value='/bin/codex'):
            found = checks.codex_checks([*checks.CODEX_CHECKS, extra], runner=fake_version)
        self.assertEqual(len(found), 2)
        self.assertTrue(found[1]['ok'], 'a later check sees what earlier ones found')


class ProbeModel(unittest.TestCase):
    MODELS = [{'id': 'gpt-6.1-sol'}, {'id': 'gpt-6-luna'}, {'id': 'gpt-5.6-luna'}]

    def test_the_learners_small_model_first(self):
        listed = mock.Mock(return_value=self.MODELS)
        self.assertEqual(checks.probe_model(Settings({'small_model': 'mini', 'model': 'big'}), listed), 'mini')
        listed.assert_not_called()

    def test_then_a_small_model_codex_offers(self):
        self.assertEqual(checks.probe_model(Settings({'model': 'big'}), lambda: self.MODELS), 'gpt-6-luna')
        self.assertEqual(checks.probe_model(Settings(broken=True), lambda: self.MODELS), 'gpt-6-luna')

    def test_then_the_teacher_model_or_codex_default(self):
        self.assertEqual(checks.probe_model(Settings({'model': 'big'}), lambda: [{'id': 'gpt-6.1-sol'}]), 'big')

        def unlisted():
            raise RuntimeError('Codex could not list models')
        self.assertIsNone(checks.probe_model(Settings(), unlisted))


class CodexAnswers(unittest.TestCase):
    def test_a_reply_passes_and_says_which_model_and_how_long(self):
        seen = []
        answer = checks.codex_answers('gpt-6-luna', runner([{'kind': 'final', 'text': 'OK'}, {'kind': 'complete'}], seen=seen))
        self.assertTrue(answer['ok'], answer)
        self.assertEqual((answer['id'], answer['model'], answer['fix']), ('answers', 'gpt-6-luna', ''))
        self.assertIsInstance(answer['seconds'], float)
        options, prompt = seen
        self.assertEqual(options, {'model': 'gpt-6-luna', 'effort': 'low', 'timeout': 60, 'idle_timeout': 30})
        self.assertEqual(prompt, checks.PROBE)

    def test_codexs_own_error_is_shown_trimmed_with_a_fix_for_any_sign_in(self):
        error = RuntimeError('Codex rejected initialization or generation; check CLI authentication and model configuration: '
                             '401 Unauthorized\n\n' + 'x' * 400)
        answer = checks.codex_answers(None, runner(error=error))
        self.assertFalse(answer['ok'])
        self.assertEqual(answer['model'], 'Codex default')
        self.assertTrue(answer['detail'].startswith('Codex rejected initialization or generation; check CLI authentication and model configuration: 401 Unauthorized x'))
        self.assertLessEqual(len(answer['detail']), 300)
        self.assertNotIn('\n', answer['detail'])
        self.assertIn('signed in, or with an API key', answer['fix'])
        self.assertNotIn('codex login', answer['fix'])

    def test_no_reply_fails(self):
        answer = checks.codex_answers(None, runner([{'kind': 'complete'}]))
        self.assertEqual((answer['ok'], answer['detail']), (False, 'Codex finished without a reply'))


if __name__ == '__main__':
    unittest.main()
