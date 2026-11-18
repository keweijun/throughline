# What stays stable from 1.0

From Throughline 1.0, a learner can update without losing anything, and someone who scripts Throughline or teaches Codex to use it can rely on what they wrote. This page lists what every 1.x release keeps. A release that breaks any of it is 2.0. Versions below 1.0 promised none of this, but the courses they made are covered too.

## Courses

- **Every course opens in every later version.** That covers courses from any 0.x release and from any 1.x. Opening one migrates it to the current format (`guided_learning/migrations.py`). Before the first step, the course is copied to `backups/course-format-<N>.sqlite3` (ADR 0007). A migration never drops learning records: answers, grades, notes, questions, memory or progress.
- **An older Throughline refuses a newer course** (`course_too_new`) and never opens it. Updating Throughline opens it again.
- **New stored data comes with a new format.** A release that stores something an older 1.x would not keep moves the course to a new format with a migration. That way an older version refuses the course rather than rewriting it without that data. Every format has a fixture course that each later version is tested against (`tests/fixtures/courses/`).

## Course packages

- A `.throughline` package from any 1.x imports into every later 1.x, at each share level (route, lessons, everything; ADR 0020).
- An older Throughline refuses a newer package (`package_too_new`) and imports nothing.

## The Codex skill's operations

The operations the skill's references describe for Codex to call (`guided_learning/skill/SKILL.md` and `references/*.md`, not the ones they tell Codex to leave to the app) are a contract with Codex and with any script that calls `guided-learning --workspace <course>`. Through 1.x:

- Every operation keeps its name, its required fields and their meaning. Its result keeps every field it returned, and its error codes keep their meaning.
- New operations, optional request fields and result fields may be added. A caller ignores fields it doesn't know.
- An operation may get stricter only where it accepted something it then mishandled, such as an exercise with no `required_concepts` or a step placed before its concepts. The new error names what is wrong.

The **chat-teaching operations** (`interaction.record`, `sidequestion.open`, `sidequestion.answer`, `sidequestion.continue`, `deferred.create`; `docs/chat-teaching-operations.md`) are deprecated and frozen. They keep working as documented through 1.x, so existing scripts and courses go on working, but they get no new features. 2.0 may remove them. The app teaches with `branch.*`, `stream.*` and its own practice jobs, which are internal to it (below).

## Commands

The `guided-learning` commands `setup`, `open`, `stop`, `courses`, `doctor`, `export` and `import`, and the flags their `--help` lists, keep their meaning. `courses` keeps the fields of its JSON output. New commands and flags may be added. `doctor`'s wording is for reading, not parsing.

## Per-user files

Settings, Studio's access and chats, and dismissed tips are kept outside the library, in the per-user config folder. Their files keep every key a version doesn't know, so running an older and a newer Throughline side by side, or going back a version, loses nothing.

## Not covered

These can change in any release:

- **The HTTP API** between the host and its own pages (`docs/architecture.md`). It ships with the pages it serves and isn't meant to be called by anything else.
- **The operations the app uses internally** and the skill's references don't list, such as `stream.*`, `branch.*`, `practice.job` and `practice.complete`.
- **What the app looks like** and how it teaches: layout, wording, prompts, and what the teacher model writes.
- **Files inside a course folder** other than the ones the learner added. Read a course through its operations, not its database.
