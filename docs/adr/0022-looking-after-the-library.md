# Courses are renamed, archived and deleted from the library

Learners have real courses and no way to look after them: a course's title is whatever Codex chose when it was built, a finished or abandoned course stays in the list for good, and the only way to remove one was to delete its folder by hand, which also throws away its progress, notes and questions. The library (ADR 0017) was meant only for opening courses; this adds what a list of a learner's own things needs, without making the library a course manager.

## Decision

Each course card in the library has a small **⋯ menu** beside its title (beside Open, until ADR 0027 made the whole card open the course and added Add files to the menu), with Rename, Archive (Unarchive for an archived course) and Delete…. They are used rarely, so none of them is a button of its own. Below the list, **Archived courses (n)** and **Deleted courses (n)** fold out what is set aside.

- **Rename** changes the course's title, in place on the card (Enter saves, Escape cancels). It is the operation `course.rename`, so it runs inside the course's transaction like any other change and can be asked of Studio too. Only the title changes: the course's id (which keys its drafts in the browser) and its folder name stay. The folder name is what everything else refers to: Studio's chats are filed by course folder in `studio.json`, `guided-learning --course <name>`, packages' suggested names and the hand-offs that name a course to Codex. A different folder name is chosen when importing a package (ADR 0020), not afterwards.
- **Archive** leaves a course out of the list and the top bar's course switcher, under Archived courses, where it can still be opened and unarchived. It is recorded in the library's own folder (`.throughline/library.json`, `{"archived": [names]}`), so nothing in the course is changed, and Codex and the `courses` command still see it. It needs no confirmation: it is undone from the notice that replaces the card ("“Thermodynamics” is archived. Undo") or from Archived courses.
- **Delete** moves the course folder, whole, to the library's trash: `.throughline/trash/<entry>/<folder name>/`, beside a `deleted.json` with its name, title and when it was deleted. It asks first, inline on the card ("Move “Thermodynamics” to the trash? Its progress, notes and questions go with it…"). The notice offers Undo, and **Deleted courses** lists what the trash holds with **Restore**. A restored course goes back under its folder name, or under the next free one (`thermo-2`) when a course of that name was made meanwhile. Its Studio chats move with it: deleting refiles them under the trash folder, so a new course with the old name does not list them, and restoring files them under the folder it comes back to.

The trash is inside `.throughline/` because everything that walks the library looks only at its top level, or skips hidden folders: the library listing and the `courses` command list folders holding `course.sqlite3`, Studio's `@` search leaves out paths starting with `.`, imports pick a free name among the library's own folders, and the library's `AGENTS.md` tells Codex never to touch `.throughline/`. A deleted course therefore takes no name, appears nowhere and is not course material.

Moving a course is never done under a write: before the move, `library.trash` leaves `.moving` in the course while holding its write lock, so a write already running (Codex registering a source from the command line, say) finishes first, and every later one finds the marker, or no course at its path, and is refused with `course_moved`. Restoring removes the marker. Setup moving courses from an old library location moves each one the same way (`moving.move_course`, which both use), leaves one Windows will not let go of where it was, takes that library's trash along, archives exactly the courses it moved from a library whose archive list named them, and deletes only the bookkeeping files it knows from the old library's own folder.

A move holds a lock beside the course, `.throughline/moving/<name>.lock`, from before it marks the course until it ends, and the operating system releases it if the process dies. So a marker in a course still in the library (not in the trash) that nobody's lock covers was left by a move that died before it renamed the folder; the next write clears it under the write lock, where no move can mark the course meanwhile, and goes ahead. Without this, a host killed at that moment left a course that refused every write, telling the learner to restore it from a trash that did not hold it. A timestamp or process ID in the marker was not chosen: a stuck move cannot be told from a dead one by age, and process IDs are reused and cannot be probed safely on Windows.

### Copies of a course folder

A course folder copied by hand keeps its course's ID, so pages do not name a course by its ID alone but by its key: the ID with a hash of the folder's path (`X-Throughline-Course`, docs/architecture.md). A page of the original is then refused by an open copy (`course_changed`) and reloads, instead of writing its notes into the copy. The copy keeps the ID, so nothing stored changes: giving a copy a new ID on open would need every course to remember where it was last opened, and would change the ID of every course moved by hand or by setup, which keys its drafts in the browser.

**Throughline never empties the trash.** Learning records are never removed by the app; a learner who wants the space back deletes folders from the trash themselves, and Deleted courses says so, with **Show the trash folder**, which opens it in the file manager. An in-app "Delete forever" would be a second, irreversible confirmation for something learners rarely need, and the large part of a course is usually Codex's working files, not the records.

### Courses in use

The host owns one open course at a time (`Courses.host`), whichever tab opened it, so "open in another tab" is that course. Studio's activity (`Studio.activity`) says whether a Studio turn runs in a course.

- Renaming is always allowed. The open course is renamed through its host, and its tabs reload their state; another course through `execute`, which Studio's turns see as any outside write.
- Archiving is always allowed, since it writes nothing in the course.
- Deleting is refused (`course_busy`) while a Studio turn runs in the course or waits on the learner, and while the open course's host writes something the learner is waiting for: a lesson, an answer, feedback or a chapter build. Background work (preparation, memory, a step written ahead) is stopped. Otherwise the open course is closed first, which releases its lease, and every tab reloads onto the library. A course held by another host, such as one started on that folder alone, is refused (`host_running`), since its folder cannot be moved safely. The refusal floats as an error; nothing is moved.

### Inline confirmations

Confirmations are shown next to what asked for them, never as a native `confirm()` popup or a modal, and only errors float (`ErrorToast`). `InlineConfirm` is that pattern: what will happen, the action (focused, so Enter confirms) and a way back (Escape cancels). It replaces the remaining `confirm()` popups: skipping a chapter, deleting a note in Notes, removing a highlight that carries a note (asked in the highlight's own toolbar) and deleting a preference from How you're taught.

## Considered and not chosen

- **Renaming the folder too.** The folder name would match the title, but Studio's chats, the `--course` name Codex was told and any hand-off already sent would point at nothing. The name is an identifier the learner rarely sees.
- **Moving archived courses to a folder of their own.** It would change their path, with the same problems as renaming the folder, for no gain over a list of names.
- **Deleting outright, or to the system's recycle bin.** Outright is not recoverable. The system bin differs by platform, needs a dependency, and a course in it would be restored without the app knowing.
- **Refusing to delete the open course.** The open course is usually the last one studied, so the learner would have to open another course first to delete it. Closing it when nothing is being written is safe.
- **Library actions in Settings.** Settings holds only what applies to every course (ADR 0017); a course's actions belong on its card.
