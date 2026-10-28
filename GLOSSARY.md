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

**Learner profile**: What the learner reported when the course was built: goal, desired depth, prior knowledge of each prerequisite (with what a quick check showed, when one was taken) and focus. It shapes the route and lesson depth. How they said they like to learn goes into course memory as preferences.
_Avoid_: Mastery, assessment, learning evidence, preferences learned during teaching (course memory).

**Pending explanation**: Content answered sufficiently for current use whose full explanation is explicitly scheduled for a later concept.
_Avoid_: Resolved, ignored question.

**Mainline restore point**: The unfinished teaching position before a branch, including the current goal, explanation progress, and remaining steps.
_Avoid_: End of chat, latest message.

**Learning section**: A part of the route that answers one core question, explaining closely related ideas together; it may span sources and turns and ends with grouped practice.
_Avoid_: Single reply, fixed page count, slide subheading, a whole chapter.

**Lesson step**: One turn of a section's lesson, teaching one part of its core question; it may end with a check question. The teacher decides how many steps a section needs and whether a step ends with a check, and may add a bridge step or reorder steps within the section (ADR 0009).
_Avoid_: Unit overview step list, a whole lesson, a slide.

**Prepared step**: The next lesson step, written while the learner reads the current one and hidden until Continue reveals it; it is not taught, shown or cited before then, and is written again when a check answer calls for a repair (ADR 0009).
_Avoid_: Preparation (of the next section), prefetch, draft step.

**Check question**: A multiple-choice question that may end a lesson step, with explanations for every option, used to catch a gap before the next step; it is never assessed and is not learning evidence.
_Avoid_: Exercise, quiz, diagnostic test.

**Exercise part**: One subquestion of an exercise, assessed on its own; an exercise is solved when all its parts are correct (ADR 0011).
_Avoid_: Step (a lesson step), a separate exercise.

**Skipped exercise**: An exercise the learner closed as too easy, too tedious or not relevant; it records no outcome and is never reminded.
_Avoid_: Deferred item ("do later" returns at review), failed, skipped section.

**Chapter**: A table-of-contents grouping of consecutive learning sections, built and revised one at a time; it is never taught as one block. A chapter with no sections is not built yet (ADR 0006).
_Avoid_: Unit (clashes with a source `unit_id`), a long lecture, a fixed number of chapters.

**Chapter overview**: The opening of a chapter's first lesson: the chapter's core problem, its sections and how they connect, links to earlier chapters, and what the learner can do at the end.
_Avoid_: An overview repeated at every section, unit overview (retired: a course without chapters is one chapter).

**Chapter recap**: An optional lesson on the chapter page that connects the chapter's sections and lists set-aside exercises without new material. It sets no questions of its own; it offers the chapter quiz (ADR 0006).
_Avoid_: Review test, chapter exam, a lesson of the chapter's last section.

**Chapter quiz**: An optional set of questions on the chapter page that mixes a few earlier exercises from the chapter's sections, asked again, with two or three new retrieval questions spanning the chapter. Each answer counts as a review of the sections it tests; it never gates the route (ADR 0008).
_Avoid_: Chapter exam, mastery test, gate, the section's exercises.

**Review**: Returning to a section the learner has passed, after a growing interval (1, 3, 7, 21, then 60 days), to answer one retrieval question about it. Reviews are listed when due, at most five a day, and never gate the route (ADR 0008).
_Avoid_: Revision of the course plan, reviewing source locations in Codex, a test that must be passed.

**Retrieval question**: A question answered from memory that asks the learner to recall a key idea and apply it to a new situation, without new material or hints. A review asks one; a chapter quiz adds two or three new ones to the earlier exercises it asks again.
_Avoid_: Flashcard, a repeat of an exercise already seen (a chapter quiz asks earlier exercises again as such, not as new questions).

**Skipped section**: A section deferred when the learner skipped the rest of its chapter or jumped past it to a later section; it stays on the route until a lesson there is studied.
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

**Course memory**: What the teacher keeps about one course: confirmed learner preferences (from teaching, or stated when the course was built), taught terms and difficulties, each citing the interactions behind it. The learner can see and edit it (ADR 0010).
_Avoid_: Learner profile (reported when the course was built), learner annotation, evidence, mastery, chat history.

**Taught term**: A term or notation recorded in course memory with the section, lesson step or side question that defined it; the teacher may use it without defining it again.
_Avoid_: Glossary of the materials, coverage ledger.

**Difficulty**: An idea the learner has repeatedly got wrong, recorded in course memory until a later check question or exercise on it is answered correctly.
_Avoid_: Needs-work assessment (one result), misconception label, weakness score.

**Teaching widget**: Part of a lesson's Markdown that the interface draws: LaTeX, highlighted code, a callout or a Mermaid diagram (the basics, always available), or an add-on (ADR 0013).
_Avoid_: Plugin, interactive simulation, embed.

**Add-on**: A teaching widget for particular subjects, such as function plots or chemical equations, from the library in this repository. Codex selects a course's add-ons; only their guides enter the teacher's instructions, while the interface draws every add-on in every course. Learners never see or manage them.
_Avoid_: Plugin (third-party code), a Settings toggle, the basic widgets.
