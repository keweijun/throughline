# Changelog

What changed for learners in each release of Throughline, newest first. Each release is tagged `v<version>` on GitHub, and the `stable` branch points at the latest one. Every pull request that bumps the version adds its entry here (AGENTS.md, Versions); CI publishes the entry as the release's notes.

## 0.50.0

- Share a course with someone, or keep a copy, from the course's Overview → **Share**: choose the route alone, the route with the lessons and exercises written so far (never your answers, progress or what the teacher remembers about you), or everything. The file always holds the course's source documents.
- **Import a course** on the library, or drop a `.throughline` file on it, shows what the file holds and asks how to take it: continue where it was left (your own course from another computer, or a backup), start fresh, or start fresh keeping the sender's notes and questions to read. A shared lesson is shown step by step as you study it, with no wait for the teacher, and every section starts unstudied.
- A shared course says what goal it was built for and offers to tell Studio yours. With Full access on, Studio warns that the course came from someone else.
- From the command line: `guided-learning export <course> --level route|lessons|everything` and `guided-learning import <file> --fresh` or `--keep-notes`.

## 0.49.3

- A course made in Studio on the library page now always finds the chat that made it in its own Studio. Before, if the page was reloaded or closed while Codex built the course, or the chat was opened again later, the chat stayed with the library and the course's Studio showed no chats.

## 0.49.2

- When Throughline closes, it now waits for its last check for changes Codex made, so it never quits with a course's database still open.

## 0.49.1

- Changes Codex makes while a lesson is streaming now always show in the open course. Since 0.48.2 one could be missed when Codex saved at the same moment as the app, and the app's own saves could reload the course for nothing.

## 0.49.0

- A figure in a lesson keeps showing the same figure after Codex reads its page again. Before, reading a page again could make an earlier lesson show a different figure from that page, when the new reading listed the figures in another order or added or left one out. Correcting a figure's crop still fixes it in every lesson that shows it.
- Reviews now count a question that tests several sections part by part: a missed part counts against its own section only, and answering the question counts as practice of every section it tests, not just the first.

## 0.48.3

- Attaching two files with the same name in Studio at the same moment no longer deletes one of them; the second is saved as `name (2)`.
- When setup moves courses from where earlier versions kept them, it now waits until Throughline has really let go of each course, and leaves a course it cannot take where it is instead of moving it while open.
- If Throughline stops just as a lesson, a side question or a "remember this" request finishes, what that turn asked course memory to keep is now recorded the next time the course opens, instead of being lost.

## 0.48.2

- Exercises, review sets, course memory and page readings that Codex saves in Studio, or in another Codex session, now show in the open course right away, instead of only after something else reloaded it.

## 0.48.1

- Code in a runnable Python cell can no longer use Throughline itself: it runs in a sealed-off part of the page, so a cell cannot read your course, turn on Studio's Full access or send Codex a message. Cells run as before, numpy and the other packages included.

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
