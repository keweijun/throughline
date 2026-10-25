# Learner annotations are private to the learner

Learners want to mark up what they study: highlight a passage, jot a quick note, bookmark a section or a source page. This keeps them in Throughline instead of copying passages into another notes app. We add these as **learner annotations**: highlights, learner notes and bookmarks, stored in the course workspace (ADR 0001) through `annotations.list`, `annotations.save` and `annotations.delete`.

## The teacher does not read them

Annotations are not sent to the teacher in lessons, side questions, practice or preparation, and they never count as learning evidence or coverage. A learner who wants the teacher to respond asks a side question, which is the existing way to bring something into the teaching.

The reason is teaching quality. An example or question the learner raises can end up anchoring later lessons: the teacher keeps returning to that analogy even when it is weak or unrelated. Feeding every highlight and scribbled note into prompts would make that much worse, because private notes are often half-formed, wrong or off-topic. Keeping annotations out of the prompt preserves the professional route-led teaching, and leaves the separate question of how much the teacher should personalize from side questions to be solved on its own.

In Codex, the skill may read annotations only when the learner asks about them directly (for example "summarize my notes on section 3"), never as context for teaching.

## Scope

- An annotation belongs to one route section, and to a passage in a lesson, a side-question answer or an exercise, a source location (exact revision and unit), or the section as a whole. A lesson, answer or exercise sets the section itself. Only the note text can be edited afterward.
- No freeform notebook, tags or sync to other apps yet. ADR 0001's "no Obsidian synchronization" still holds. The Notes tab can export the shown notes (a section, a chapter or the course) as a one-way Markdown download; nothing is read back.
