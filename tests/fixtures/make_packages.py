"""Writes a course package of the current fixture course at each share level, as tests/fixtures/packages/
package-<format>-<level>.throughline (ADR 0020), which tests/test_package_fixtures.py imports with every later version.

Run this when a change raises the package format (`guided_learning.packages.FORMAT`), and commit the files:

    .venv/bin/python -m tests.fixtures.make_packages

The course is the newest tests/fixtures/courses fixture with its stored paths under a made-up library folder, so the
package names no folder of the machine that wrote it.
"""
import re
import sys
import tempfile
from pathlib import Path
from unittest import mock

from guided_learning import migrations, packages
from tests.test_course_fixtures import FIXTURES, load

OUT = Path(__file__).resolve().parent / 'packages'
ROOT = Path(__file__).resolve().parents[2]
STORED = '/learner/Throughline/quantum'


def main():
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        course = Path(scratch).resolve() / 'quantum'
        load(FIXTURES / f'format-{migrations.VERSION}.sql', course, stored=STORED)
        # The manifest names the version that wrote it: this checkout's, whatever version the environment installed.
        written_by = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M)[1]
        with mock.patch('guided_learning.commands.version', return_value=written_by):
            for level in packages.LEVELS:
                target = OUT / f'package-{packages.FORMAT}-{level}.throughline'
                packages.export(course, target, level)
                print(target)


if __name__ == '__main__':
    sys.exit(main())
