# Courses are shared and moved as course packages

Learners want to give a course to a classmate, and to move or back up their own. The only way so far is copying the course folder (ADR 0007), which has three problems. A live course uses write-ahead logging, so a copy can miss recent writes. The folder carries Codex's working files (in one real course, `audit/` was 349 MB beside an 11 MB `sources/` folder) and the host's lease file. And a copy is all or nothing: the classmate gets the sender's progress, course memory, questions and notes, and the teacher then treats them as the sender.

A **course package** is one file, `<course>.throughline`, made by `guided-learning export` and read by `guided-learning import`, which Studio can also run on request. They are commands rather than course operations because an import makes a new course and an export reads the whole folder, while an operation works inside one course's transaction. The export is on the Course page; the import is on the library, beside New course, and accepts a package dropped on the library. Throughline is still for one learner per course (ADR 0004): a package is a copy, and nothing syncs back.

## Share levels

The sender picks how much the package holds:

| Level | Holds | Leaves out |
|---|---|---|
| **Route** | The course's title and language, the route and chapters with each section's goal and overview, coverage, the sources with their page readings and checks, and the selected add-ons | Every lesson and exercise; the recipient's teacher writes them |
| **Route and lessons** | The above, plus lessons (every lesson step with its plan and check question) and chapter recaps, and exercises without the sender's answers, feedback or status | Check answers, exercise attempts, preparation material, review sets and chapter quizzes |
| **Everything** | The whole course: progress, evidence, course memory, side questions and learner annotations | Only what no level carries (below) |

Below Everything, the package also carries the sender's learner profile as a read-only **built for** note ("a 6–8 hour exam preparation at standard depth"). It is not the recipient's profile. The route was shaped by it, so after importing, the Course page asks the recipient for their own goal, and Studio can reshape the route from it.

A lesson step written after the sender missed a check question opens with a repair aimed at that miss (ADR 0009). Route and lessons keeps those steps as written; rewriting them is not worth a teacher turn.

Before exporting Everything, the export lists what it shares (for example "12 notes, 40 questions, your progress"), since annotations are otherwise private (ADR 0005).

## Importing

The recipient picks how much to take, up to the package's level. An Everything package offers three choices:

- **Continue where they left off.** The course as it was: progress, course memory and annotations. This is a backup restored or a course moved to another computer.
- **Start fresh.** The course at Route and lessons.
- **Start fresh, keep their notes and questions to read.** As Start fresh, plus the sender's learner annotations and side questions, shown as the sender's and read-only. Like annotations (ADR 0005), they never enter the recipient's teaching prompts, so another learner's questions do not anchor their lessons.

The choice is made on import, not on export, because only the recipient knows whether they are the sender on a new computer or someone else.

An imported course gets a new id and a folder name of the recipient's choosing. It is marked as imported from someone else unless it is continued, and Studio warns when Full access is on in such a course: its sources and lessons reach Codex's prompts, and a crafted package could try to steer Codex.

## Sources travel with the package

Every package holds the sources' files, at every level. Teaching is led by the sources: lessons follow their pages in order and depth (ADR 0009), and citations, page readings, figures, coverage and exercises taken from problem sets all point into them. A course without its sources would be taught from section goals alone. The export says that the files are shared and that the learner must be allowed to share them.

A source's id is derived from the path it was registered from, which means nothing on another computer. Sources in an imported course point at their stored copy instead, and registering a file matches an existing source by its content (the revision) before its path, so a recipient who adds the same PDF from their own folder updates that source rather than adding a second one.

## What no level carries

A package holds the course's records, its sources' stored files and, with the records that use them, attached images (`answer_images/`), and nothing else from the folder. So it never carries Studio threads (they live in the sender's Codex home, ADR 0016), files Codex wrote while working (such as `audit/`, `inputs/` and `import-requests.jsonl`), rendered page images (`page_images/`, drawn again when needed), the host's lease file and per-user settings.

## Format

A ZIP holding `manifest.json` (package format version, course schema version, Throughline version, level, title, language, the built-for note and each source's revision), `course.sqlite3`, `sources/` and the attached images the records it holds refer to. An Everything export copies the database with SQLite's backup API, so it is consistent while the course is open. The lower levels write a new database containing only the records their level lists.

Importing treats the package as untrusted. Entries that would land outside the new course folder, or that unpack far beyond their compressed size, are refused. Records are read into a database the importer creates, so a crafted database file is never opened as a course. Versions follow ADR 0007: an older package migrates on its first operation, and a package whose course schema is newer than the app is refused with `course_too_new` before anything is unpacked.

Every record namespace belongs to a level, or to none. A test fails when a namespace is added without a level, so a new kind of learner data cannot leak into a shared course by default.

## Considered and not chosen

- **Copying the folder** (ADR 0007's way until now). It stays possible for a closed course, but it carries the problems above.
- **Sources optional**, so a package could leave out files the sender may not share, and the recipient would register their own copies, matched by revision. Without its sources a course teaches badly until every file is added again, and most courses are built from the learner's own lecture notes. It can be added later on the same matching.
- **Export as JSON documents** instead of a database. It is readable, but it would need its own versioning beside ADR 0007's migrations, while a database in the package migrates like any course.
- **A separate backup feature.** A backup is an Everything package continued on import.
- **Choosing between continue and start fresh on export.** The sender cannot know whether the package will be opened by them on a new computer or by someone else.
