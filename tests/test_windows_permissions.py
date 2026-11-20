"""On Windows, the host key and the host's output log are limited to this user by their ACL: POSIX modes set none there,
so the files would take the library folder's permissions (SECURITY.md)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guided_learning import library


def entries(path):
    """The ACL entries icacls lists for a file, as 'ACCOUNT:(rights)' strings."""
    shown = subprocess.run(['icacls', str(path)], capture_output=True, check=True).stdout.decode('utf-8', 'replace')
    found = []
    for line in shown.splitlines():
        line = line.replace(str(path), '', 1).strip() if not found else line.strip()
        if ':(' in line:
            found.append(line)
    return found


@unittest.skipUnless(os.name == 'nt', 'Windows ACLs')
class WindowsPermissions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {'GUIDED_LEARNING_HOME': self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.me = subprocess.run(['whoami'], capture_output=True, check=True).stdout.decode('utf-8', 'replace').strip().lower()

    def assert_only_me(self, path):
        found = entries(path)
        self.assertEqual(len(found), 1, found)
        self.assertNotIn('(I)', found[0], 'nothing inherited from the folder')
        account, rights = found[0].split(':(', 1)
        self.assertEqual(account.lower(), self.me)
        self.assertTrue(rights.startswith('F)'), found)

    def test_a_new_host_key_is_readable_by_this_user_alone(self):
        library.host_key()
        self.assert_only_me(library.state_dir() / 'host.key')

    def test_a_key_an_earlier_version_made_is_limited_when_read(self):
        path = library.state_dir() / 'host.key'
        path.parent.mkdir(parents=True)
        path.write_text('d' * 64, encoding='ascii')
        subprocess.run(['icacls', str(path), '/grant', '*S-1-5-32-545:R'], capture_output=True, check=True)  # Users may read it
        self.assertGreater(len(entries(path)), 1)
        library._kept_private.discard(path)
        self.assertEqual(library.host_key(), 'd' * 64)
        self.assert_only_me(path)

    def test_any_file_can_be_kept_private(self):
        path = Path(self.tmp.name) / 'host-output.log'
        path.write_text('started', encoding='utf-8')
        library.keep_private(path)
        self.assert_only_me(path)


if __name__ == '__main__':
    unittest.main()
