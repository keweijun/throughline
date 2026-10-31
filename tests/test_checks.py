"""The checks of what Throughline needs from Codex, run against a fake Codex."""
import subprocess
import unittest
from unittest import mock

from guided_learning import checks


def fake_codex(signed_in=True, login_code=None):
    calls = []

    def run(command):
        calls.append(command[1:])
        if command[1:] == ['--version']:
            return subprocess.CompletedProcess(command, 0, 'codex-cli 0.164.0\n', '')
        code = login_code if login_code is not None else 0 if signed_in else 1
        return subprocess.CompletedProcess(command, code, 'Logged in using ChatGPT\n' if code == 0 else 'Not logged in\n', '')
    return run, calls


class CodexChecks(unittest.TestCase):
    def test_all_pass(self):
        run, calls = fake_codex()
        with mock.patch.object(checks.codex, 'find_codex', return_value='/bin/codex'):
            found = checks.codex_checks(runner=run)
        self.assertEqual([(c['id'], c['ok']) for c in found], [('codex', True), ('signed_in', True)])
        self.assertEqual(found[0]['detail'], 'codex-cli 0.164.0 (/bin/codex)')
        self.assertEqual(calls, [['--version'], ['login', 'status']])
        self.assertTrue(all(c['fix'] == '' for c in found))

    def test_not_signed_in_says_how_to_sign_in(self):
        run, _ = fake_codex(signed_in=False)
        with mock.patch.object(checks.codex, 'find_codex', return_value='/bin/codex'):
            signed_in = checks.codex_checks(runner=run)[1]
        self.assertFalse(signed_in['ok'])
        self.assertIn('codex login', signed_in['fix'])
        self.assertEqual(signed_in['detail'], 'Not logged in')

    def test_without_codex_sign_in_is_not_checked(self):
        run, calls = fake_codex()
        with mock.patch.object(checks.codex, 'find_codex', return_value=None):
            found = checks.codex_checks(runner=run)
        self.assertEqual([(c['id'], c['ok']) for c in found], [('codex', False)])
        self.assertIn('Install Codex', found[0]['fix'])
        self.assertEqual(calls, [])

    def test_an_answer_that_is_not_yes_or_no_shows_nothing(self):
        for failure in (dict(login_code=2), dict(error=subprocess.TimeoutExpired('codex', 15))):
            run, _ = fake_codex(login_code=failure.get('login_code'))
            if 'error' in failure:
                real = run

                def run(command, real=real, error=failure['error']):
                    if command[1:] == ['login', 'status']:
                        raise error
                    return real(command)
            with mock.patch.object(checks.codex, 'find_codex', return_value='/bin/codex'):
                self.assertEqual([c['id'] for c in checks.codex_checks(runner=run)], ['codex'], failure)

    def test_a_codex_that_does_not_run_fails(self):
        def run(command):
            raise FileNotFoundError(command[0])
        with mock.patch.object(checks.codex, 'find_codex', return_value='/missing/codex'):
            found = checks.codex_checks(runner=run)
        self.assertEqual([(c['id'], c['ok'], c['detail']) for c in found], [('codex', False, '/missing/codex')])

    def test_later_work_can_add_a_check(self):
        extra = lambda context: checks.result('codex', context.get('codex') == '/bin/codex')
        run, _ = fake_codex()
        with mock.patch.object(checks.codex, 'find_codex', return_value='/bin/codex'):
            found = checks.codex_checks([*checks.CODEX_CHECKS, extra], runner=run)
        self.assertEqual(len(found), 3)
        self.assertTrue(found[2]['ok'], 'a later check sees what earlier ones found')


if __name__ == '__main__':
    unittest.main()
