# Changelog

What changed for learners in each release of Throughline, newest first. Each release is tagged `v<version>` on GitHub, and the `stable` branch points at the latest one. Every pull request that bumps the version adds its entry here (AGENTS.md, Versions); CI publishes the entry as the release's notes.

## 0.48.0

- When a course file moves, or you add your own copy of a file that an imported course already has, Throughline now keeps the existing source, with its page readings and its place in the route, instead of adding a second one. Two copies you register on purpose still stay two sources.

## 0.47.0

- A whole course can be saved to one file and opened again as a new course, with its progress, course memory, notes and sources: `guided-learning export <course>` writes `<course>.throughline`, and `guided-learning import <file>` adds it to the library. Use it to back a course up or move it to another computer; Codex can do it from Studio when asked. The file holds only the course, not Codex's working files, so it is far smaller than the course folder.

## 0.46.0

- Before updating a course to a new storage format, Throughline now keeps a copy of it as it was in the course's `backups/` folder. If an update goes wrong, the copy and the earlier Throughline version bring the course back (see ADR 0007). A course that cannot be copied, on a full disk for example, is not updated.
- One damaged course no longer stops the library from listing the others; it is listed with what went wrong, and Throughline no longer keeps its file open, so on Windows it can be replaced while Throughline runs.
- When the library or a course cannot be loaded, the page says why and offers Try again, instead of waiting forever or staying blank.
- Unsent text (side questions, notes, exercise answers, Studio messages) now stays with its own course, and is kept after the browser is closed.

## 0.45.0

- Installing and updating now fetch the latest release (the `stable` branch) instead of whatever is on `main`, so learners only ever get a version that passed the tests on Linux, macOS and Windows. Each release is tagged, so `@v0.45.0` in place of `@stable` installs a particular version.
- The update check in Settings → About compares with the latest release.
- The license notices of the bundled interface code, including CodeMirror's, now ship inside the installed package.
- On Windows, `guided-learning setup --language zh-CN` no longer stops before the Chinese welcome guide when its output goes to Codex: the command now always writes UTF-8.

## Earlier versions

Versions before 0.45.0 were not tagged; their changes are in the [merged pull requests](https://github.com/keweijun/throughline/pulls?q=is%3Apr+is%3Amerged).
