"""Release checks and notes for CI (ADR 0020). Not part of the installed package.

    python scripts/release.py version          the version in pyproject.toml
    python scripts/release.py check <base>     fails a PR that changes what learners install without a newer version
                                               and a CHANGELOG.md entry for it
    python scripts/release.py notes <version>  the CHANGELOG.md entry for a version, for its GitHub release
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
# What `pip install` takes from the repository: the package, its metadata and the license files it ships.
SHIPPED = ('guided_learning/', 'licenses/', 'pyproject.toml', 'LICENSE', 'THIRD_PARTY_LICENSES.md')


def version(text):
    match = VERSION.search(text)
    if not match:
        sys.exit('No version in pyproject.toml')
    return match.group(1)


def parts(text):
    return tuple(int(n) for n in re.findall(r'\d+', text))


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding='utf-8').stdout


def notes(text, wanted):
    """The body under `## <version>` (a date or note may follow the version on that line), up to the next heading."""
    match = re.search(rf'^## v?{re.escape(wanted)}\b[^\n]*\n(.*?)(?=^## |\Z)', text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else None


def check(base):
    current = version((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    before = version(git('show', f'{base}:pyproject.toml'))
    changed = [p for p in git('diff', '--name-only', f'{base}...HEAD').splitlines() if p.startswith(SHIPPED)]
    problems = []
    if changed and parts(current) <= parts(before):
        problems.append(f'This changes what learners install ({", ".join(changed[:5])}{", ..." if len(changed) > 5 else ""}) '
                        f'but the version is {current}, not above {before} on {base}. Bump it in pyproject.toml (AGENTS.md, Versions).')
    if current != before and not notes((ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'), current):
        problems.append(f'CHANGELOG.md has no "## {current}" entry.')
    if problems:
        sys.exit('\n'.join(problems))
    print(f'Version {current} ({before} on {base}); {len(changed)} shipped files changed.')


def main(argv):
    if argv[:1] == ['version']:
        print(version((ROOT / 'pyproject.toml').read_text(encoding='utf-8')))
    elif len(argv) == 2 and argv[0] == 'check':
        check(argv[1])
    elif len(argv) == 2 and argv[0] == 'notes':
        found = notes((ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'), argv[1])
        if found is None:
            sys.exit(f'CHANGELOG.md has no "## {argv[1]}" entry')
        print(found)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
