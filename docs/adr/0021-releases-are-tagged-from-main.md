# Releases are tagged from main, and learners install the latest release

Until 0.45.0 a release was only a version bump on `main`: the installers, the README's steps and the one-click update installed whatever `main` held at that moment, and the update check read `main`'s `pyproject.toml` (ADR 0004). So a commit merged without a bump still reached every new install, the version announced could differ from the one installed, there was nothing to go back to, and no test ran on Windows or macOS before learners got the code.

## Decision

- **CI tests every pull request and every push to `main`** (`.github/workflows/ci.yml`): the Python tests on Linux (the oldest supported Python and a recent one), macOS and Windows; the browser tests; the type check, the license-notice check and a check that the committed `guided_learning/web_dist` is the build of `web/src`. A pull request that changes what learners install (`guided_learning/`, `pyproject.toml`, the license files) must raise the version above `main`'s and add a `## <version>` entry to `CHANGELOG.md` (`scripts/release.py check`).
- **A release is a version bump merged to `main` that passes CI.** The release job then tags the commit `v<version>`, publishes a GitHub release with the changelog entry as its notes, and moves the `stable` branch to it. The job only ever fast-forwards `stable`; a run for a version already released just makes sure `stable` has reached it.
- **Learners install `stable`.** The installers, the README's steps (which the one-click update follows) and the skill install `git+https://github.com/keweijun/throughline@stable`, and the update check reads `stable`'s `pyproject.toml`. A tag in place of `stable` installs a particular version.

The bump rules stay as AGENTS.md states them; what changes is that a merged bump is published only once it has passed CI, and that unbumped commits on `main` no longer reach learners.

## Considered

- **Tags only, with installers looking up the latest release through GitHub's API.** It removes the branch, but every installer, the README's steps and the update check would need that lookup, and the unauthenticated API is rate limited. A branch keeps the install command one fixed line.
- **Publishing to PyPI.** The name `throughline` belongs to an unrelated project there, and installing from GitHub needs no account or upload step. It can come later under another name.
- **Releasing by hand.** A forgotten tag would leave learners on an old version, and the bump in each pull request already says when a release is meant.

## Consequences

Installs from before 0.45.0 read `main`'s version to find updates; they still update correctly, because the update follows the README, which now installs `stable`. If CI fails on `main`, nothing is released until a fix is merged. Going back to an older tag cannot open a course a newer version has already migrated (ADR 0007).
