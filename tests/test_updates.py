import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guided_learning import updates
from support import host_client


def course(path):
    from guided_learning.api import execute
    execute(path, {'op': 'course.init', 'title': 'Quantum'})


class UpdateCheck(unittest.TestCase):
    def test_versions_compare_by_number_and_a_checkout_is_never_behind(self):
        self.assertTrue(updates.newer('0.10.0', '0.9.3'))
        self.assertTrue(updates.newer('0.5.2', '0.5.1'))
        self.assertFalse(updates.newer('0.5.1', '0.5.1'))
        self.assertFalse(updates.newer('0.5.0', '0.5.1'))
        self.assertFalse(updates.newer('0.6.0', 'development'))

    def test_the_host_reports_main_s_declared_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / 'pyproject.toml'
            remote.write_text('[project]\nname = "throughline"\nversion = "9.0.0"\n', encoding='utf-8')
            course(Path(tmp) / 'course')
            client, _ = host_client(Path(tmp) / 'course')
            with client, mock.patch.dict(os.environ, {'GUIDED_LEARNING_UPDATE_URL': remote.as_uri()}), \
                    mock.patch.object(updates, 'version', return_value='0.5.1'):
                result = client.get('/api/update').json()
                self.assertEqual(result, {'version': '0.5.1', 'latest': '9.0.0', 'available': True})
                remote.write_text('version = "0.5.1"\n', encoding='utf-8')
                self.assertFalse(client.get('/api/update').json()['available'])
                remote.unlink()
                missing = client.get('/api/update')
                self.assertEqual(missing.status_code, 502)
                self.assertEqual(missing.json()['code'], 'update_check_failed')


if __name__ == '__main__':
    unittest.main()
