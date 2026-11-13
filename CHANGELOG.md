# Changelog

What changed for learners in each release of Throughline, newest first. Each release is tagged `v<version>` on GitHub, and the `stable` branch points at the latest one. Every pull request that bumps the version adds its entry here (AGENTS.md, Versions); CI publishes the entry as the release's notes.

## 0.42.0

- Installing and updating now fetch the latest release (the `stable` branch) instead of whatever is on `main`, so learners only ever get a version that passed the tests on Linux, macOS and Windows. Each release is tagged, so `@v0.42.0` in place of `@stable` installs a particular version.
- The update check in Settings → About compares with the latest release.
- The license notices of the bundled interface code, including CodeMirror's, now ship inside the installed package.
- On Windows, `guided-learning setup --language zh-CN` no longer stops before the Chinese welcome guide when its output goes to Codex: the command now always writes UTF-8.

## Earlier versions

Versions before 0.42.0 were not tagged; their changes are in the [merged pull requests](https://github.com/keweijun/throughline/pulls?q=is%3Apr+is%3Amerged).
