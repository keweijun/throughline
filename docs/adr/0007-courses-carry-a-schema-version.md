# Courses carry a schema version and migrate forward

Learners already have courses on disk, and courses move between computers by copying the folder (ADR 0004). Until now the course format changed implicitly: code read missing fields with fallbacks and "existing courses open without migration" (ADR 0003). That works for additive fields but not for reshaping stored data, backfilling a field that new features depend on, or protecting a course from an older app that does not understand it.

Each course workspace stores `course/schema` = `{"version": N}`. `guided_learning/migrations.py` holds an ordered list of migrations, each a function `(store) -> None` that moves the course from version N-1 to N. Courses without the record are version 1, the format before versioning.

- `execute` reads the version at the start of every operation, inside the operation's transaction. If it is older than the code's version it runs the pending migrations in order and records the new version before handling the request, under `BEGIN IMMEDIATE`, so a migration commits or rolls back with that first operation. (A read-only operation runs without the write lock; when it finds an older version it is run again as a write, so the migration still happens first.) `course.init` on a new course records the current version directly.
- A course whose version is newer than the code fails every operation with `course_too_new` and a message to update Throughline. An older app never writes to a newer course.
- Migrations only move data forward; there is no downgrade. They must be idempotent on partially migrated data, preserve learning evidence and raw interactions, and keep every operation's name and semantics (the stable contract in AGENTS.md).
- The course library lists such a course with that message instead of opening it. Listing a course runs its pending migrations like any other operation.

Copying a course to a computer with an older Throughline now gives a clear "update Throughline" error instead of silent misreads. The cost is one small read per operation and the discipline of writing a migration plus a test with an old-format fixture whenever stored data changes shape.

The first migration (version 2) replaces the whole lesson record that each side question copied into `selected_lecture`, and into every answer's prompt snapshot, with the lesson's id, section, title, text and source references.
