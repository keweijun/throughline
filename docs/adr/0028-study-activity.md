# Study activity is worked out from what courses already record, and shows what happened without anything to keep up

A learner asked to see their studying over time. A course already records when most of what the learner does happened: each lesson step, exercise turn, side question and drill message is a stream turn with the time the learner asked for it; check and recall answers carry `answered_at` and `at`; notes carry `created_at`. Nothing records time spent, and earlier decisions dropped due dates, counts and time budgets because they turned studying into chores (ADR 0014).

## Decision

- **Settings → Activity**, between Teacher and About, covers every course in the library. It spans courses and is looked at now and then, so it stays off the library page and out of the working places (ADR 0017).
- **No new tracking.** `GET /api/activity` reads each course's database read-only (`?mode=ro`, as `library.fingerprint` does; no migration, no lock, a course being moved skipped) and returns each course's activity as `[time, kind]` pairs, kind being a lesson step, an answer, a question, a note or a drill message. Results are cached by the database's stamp, like library summaries.
- **Only what the learner did counts.** Background channels (preparation, builds, consolidation, memory, key points, chapter sheets) are left out. A step written ahead counts when the learner reveals it (`revealed_at`). An exercise counts when it is worked on or answered, not when the teacher wrote it. A course imported fresh from someone else counts from its import (`course/imported.at`), and the sender's notes that came with it (`from_sender`) not at all. A course carried on from a package keeps its history, which is the learner's own.
- **Days and time are worked out in the browser**, in the learner's time zone. Time studied is an estimate and says so: actions less than 20 minutes apart are one sitting, which lasts from its first action to its last plus 3 minutes for that last one; a day's time merges every course's actions, so switching courses is not counted twice.
- **The page shows what happened.** A calendar of the last 26 weeks, each day's square a deeper shade for more time (fixed steps: under 15, 45 and 90 minutes, and more, so a square means the same every week); the chosen day's courses with their counts and time; and each course's last day studied and time in the six months.
- **Nothing to keep up.** No streaks, goals, averages to beat, or marks for days missed.

## Considered and rejected

- **Tracking time on screen.** It needs a new record written while studying, counts a tab left open, and courses would have no history until it shipped. The estimate is honest about being one.
- **Where the learner stands** (sections studied, exercises right and wrong, open mistakes). Learn and Review already show progress where it is used; the learner asked for activity.
- **Codex usage** (turns and tokens per course). Not asked for.
- **A summary on the library page or in the course.** The library page stays sparse (ADR 0027), and a course's places are for studying in it.

## Consequences

- Courses studied in Codex chat before the app, and records from versions that kept no times, show no activity.
- A turn regenerated later moves to the time of the retry.
- `/api/activity` is a library route; it reads every course on each visit to the page, which the stamp cache keeps cheap for courses that have not changed.
