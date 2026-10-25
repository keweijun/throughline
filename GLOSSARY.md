# Personal cross-document guided learning

Concepts for organizing multiple materials around one learning goal and preserving teaching continuity through interaction.

## Language

**Cross-document guided learning**: Organizing and advancing one learning goal using knowledge connections and prerequisites across multiple sources.
_Avoid_: Calling multi-file question answering or file selection alone cross-document guided learning.

**Deferred item**: Content the learner chooses to skip temporarily that remains in scope for later learning or review.
_Avoid_: Mastered, completed, permanently excluded.

**Teaching mainline**: The active learning goal and the sequence of explanations and practice organized to achieve it.
_Avoid_: Chat history, slide file order.

**Side question**: A local question or extension raised during the teaching mainline, whose scope depends on the current goal and course route.
_Avoid_: Off-topic, irrelevant question.

**Route-aware question answering**: Choosing side-question depth using the current goal, prerequisites, upcoming topics, and known difficulties while preserving teaching continuity.
_Avoid_: Always brief, always detailed, depth determined by question length.

**Learner profile**: What the learner reported when the course was built: goal, desired depth, prior knowledge of each prerequisite and focus. It shapes the route and lesson depth.
_Avoid_: Mastery, assessment, learning evidence.

**Pending explanation**: Content answered sufficiently for current use whose full explanation is explicitly scheduled for a later concept.
_Avoid_: Resolved, ignored question.

**Mainline restore point**: The unfinished teaching position before a branch, including the current goal, explanation progress, and remaining steps.
_Avoid_: End of chat, latest message.

**Learning section**: A part of the route that answers one core question, explaining closely related ideas together; it may span sources and turns and ends with grouped practice.
_Avoid_: Single reply, fixed page count, slide subheading, a whole chapter.

**Chapter**: A table-of-contents grouping of consecutive learning sections, built and revised one at a time; it is never taught as one block. A chapter with no sections is not built yet (ADR 0006).
_Avoid_: Unit (clashes with a source `unit_id`), a long lecture, a fixed number of chapters.

**Chapter overview**: The opening of a chapter's first lesson: the chapter's core problem, its sections and how they connect, links to earlier chapters, and what the learner can do at the end.
_Avoid_: An overview repeated at every section, unit overview (retired: a course without chapters is one chapter).

**Chapter recap**: An optional lesson at the end of a chapter that connects its sections and lists set-aside exercises, without new material or exercises.
_Avoid_: Quiz, review test, chapter exam.

**Skipped section**: A section deferred when the learner skipped the rest of its chapter; it stays on the route until a lesson there is studied.
_Avoid_: Excluded, completed, mastered.

**Course library**: The learner's Throughline folder holding every course workspace; and the app view that lists courses for opening. The view never edits a course; changes happen in Codex.
_Avoid_: Course manager, a second store of progress.

**Coverage ledger**: A list linking teaching content in the materials to concepts, source locations, and inclusion or deferral decisions; it does not establish learner mastery.
_Avoid_: Mastery, reading progress.

**Learning companion panel**: A view alongside the teaching conversation that continually presents course structure, current position, and related materials.
_Avoid_: A second course with separate progress, a complete chat mirror.

**Preparation material**: Goals, source checks, teaching points, examples, exercises, and uncertainty notes prepared for a learning section and used by the teacher during instruction.
_Avoid_: A final script that must be read verbatim, evidence of learner mastery.

**Preparation readiness**: The preparation material for a section is sufficient to begin teaching it.
_Avoid_: Learning completed, mastered, all sources permanently valid.

**Learner annotation**: A highlight, learner note or bookmark the learner keeps for themselves, attached to a route section and optionally to a passage or source location. The teacher does not read it (ADR 0005).
_Avoid_: Notebook, evidence, side question, deferred item.

**Highlight**: A learner annotation marking a passage in a lesson, side-question answer, exercise or source, optionally with a note.
_Avoid_: Asked passage (a passage quoted in a side question).

**Learner note**: Text the learner writes on a highlight or on a whole section.
_Avoid_: Uncertainty notes in preparation material, progress note.

**Bookmark**: A learner annotation marking a section or a source location to come back to.
_Avoid_: Deferred item, mainline restore point.
