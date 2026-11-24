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

**New lesson**: Another stepped lesson for a section that already has one, planned again from the section as it now stands and focused by the learner's request; it replaces the section's lesson, which stays with the section, read-only and marked as replaced (ADR 0023).
_Avoid_: Another pass (one reply added to the lesson that is there), regenerating a step, a new section.

**Prepared step**: The next lesson step, written while the learner reads the current one and hidden until Continue reveals it; it is not taught, shown or cited before then, and is written again when a check answer calls for a repair (ADR 0009).
_Avoid_: Preparation (of the next section), prefetch, draft step.

**Check question**: A multiple-choice question that may end a lesson step, with explanations for every option, used to catch a gap before the next step; it is never assessed and is not learning evidence.
_Avoid_: Exercise, quiz, diagnostic test.

**Exercise part**: One subquestion of an exercise, assessed on its own; an exercise is solved when all its parts are correct (ADR 0011).
_Avoid_: Step (a lesson step), a separate exercise.

**Explanation exercise**: An exercise asking the learner to explain an idea in their own words to a stated reader, assessed by its ideas rather than its wording (ADR 0011).
_Avoid_: Paraphrase, ritual restatement, a separate kind of record.

**Skipped exercise**: An exercise the learner closed as too easy, too tedious or not relevant; it records no outcome and is never reminded.
_Avoid_: Deferred item ("Do later" stays in scope and enters the review context), replaced exercise, failed, a section not studied.

**Replaced exercise**: An exercise the teacher wrote that the learner had not touched, replaced when they asked for different exercises; it is kept for the record but no longer shown. The course's own exercises are never replaced.
_Avoid_: Skipped exercise, deleted, regenerated homework.

**Retired exercise**: An exercise the learner never touched that Codex took out of its section, such as a duplicate; it is kept for the record but no longer shown, counted or asked again (ADR 0011).
_Avoid_: Skipped exercise (the learner closed it), replaced exercise, deleted.

**Chapter**: A table-of-contents grouping of consecutive learning sections, built and revised one at a time; it is never taught as one block. A chapter with no sections is not built yet (ADR 0006).
_Avoid_: Unit (clashes with a source `unit_id`), a long lecture, a fixed number of chapters.

**Chapter overview**: The opening of a chapter's first lesson: the chapter's core problem, its sections and how they connect, links to earlier chapters, and what the learner can do at the end.
_Avoid_: An overview repeated at every section, unit overview (retired: a course without chapters is one chapter).

**Key point**: One result, rule, definition or method a learner should hold from a studied section, written by the teacher: its statement, when it holds and a common mistake, linked to the lesson step and source pages that taught it. The learner does not edit key points; they ask Codex to change them (ADR 0024).
_Avoid_: Summary, flashcard, the learner's notes, a mastery target.

**Chapter sheet**: A chapter's key points gathered on its chapter page, in route order, opened by a short paragraph on how its sections connect (ADR 0024).
_Avoid_: Chapter recap, cheat sheet (something the learner asks Studio to make), chapter summary (the outline's one-line description).

**Chapter recap**: Retired: a lesson on the chapter page, started on request, that connected the chapter's sections. Key points and the chapter sheet replace it; recaps written before stay readable (ADR 0006, ADR 0024).
_Avoid_: Using it for the chapter sheet.

**Chapter quiz**: Retired: a review set scoped to one chapter, taken from the chapter page, that asked earlier exercises again with new questions spanning the chapter. **Drill this chapter**, a drill session scoped to the chapter, replaces it; quizzes taken before stay on the chapter page (ADR 0025).
_Avoid_: Chapter exam, mastery test, gate, the section's exercises.

**Review**: Going over sections already studied, in the Review place, when the learner chooses: reading key points, the mistakes book, or a drill session over a review scope. There is no schedule and nothing comes due (ADR 0014, ADR 0025).
_Avoid_: Revision of the course plan, reviewing source locations in Codex, a test that must be passed, a due list.

**Review scope**: What the Review place covers: everything studied, or the chapters and sections the learner chose. Key points, the mistakes book and the questions asked there all follow it, and the course remembers the last choice in the learner's browser (ADR 0014).
_Avoid_: A review set's own scope (what one request asked about), a filter on the route.

**Mistakes book**: The learner's misses, collected on the Review page from what the course records: missed exercise, chapter-quiz and review parts, wrong recall answers, and ideas whose check questions were missed more than once. An entry the learner later gets right stays, marked with when; nothing is counted or cleared (ADR 0014).
_Avoid_: Error log, to-do list, a single missed check question (a slip, not yet a mistake).

**Review set**: Retired: the questions written for one review request before drill sessions. Sets written before stay to read and answer (ADR 0025).
_Avoid_: Using it for a drill session.

**Hand-off**: A request a fast view (a lesson, a drill, the Review place) cannot serve, sent to Studio as a new chat with where it came from; the learner stays put and the card that sent it follows the chat (ADR 0026).
_Avoid_: Escalation (internal), redirect, a link that only opens Studio.

**Way to review**: How a drill session asks, chosen in the Review place: quick questions, explain it back, oral quiz or telling confusable ideas apart; Studio ways (a mock exam, a sheet) are hand-offs (ADR 0026).
_Avoid_: Mode, game, a separate page.

**Sheet**: A page Codex wrote in Studio for review, such as a cheat sheet, a formula sheet or the learner's mistakes on one page. It covers chapters or sections, is read and printed in Review's Sheets, and is linked from the chapter page (ADR 0026).
_Avoid_: Chapter sheet (the chapter's key points), key points, a source.

**Drill session**: A conversation with the fast teacher over a review scope, in the Review place: it asks a few review questions at a time, the learner answers them in place, asks for more or says what to drill next. It is kept and reopened at will and never finished or due; a chapter's drill and a warm-up are sessions with a fixed scope (ADR 0025).
_Avoid_: Quiz, test, review set, a session that must be completed.

**Fast teacher**: The teacher of a drill session, running on the small model so a reply comes quickly; its assessments count as evidence like any teacher's (ADR 0025).
_Avoid_: A second teacher with its own memory, Studio.

**Review context**: What the teacher is given to choose review questions: for each studied section when it was last practised, recent misses and exercises set aside, plus course memory and earlier review questions with their outcomes; a drill session adds its scope's key points and open mistakes. It informs, it never schedules.
_Avoid_: Review schedule, due dates, mastery score.

**Warm-up**: A short drill session offered when the learner opens a section whose prerequisites were studied but not practised for a while, scoped to those prerequisites and shown on the section. Offered once per section and never required (ADR 0025).
_Avoid_: Pre-test, gate, the chapter overview.

**Retrieval question**: A review question answered from memory, without new material or hints in the question: a recall question (multiple choice or a short answer, with instant feedback, not evidence) or an apply question (a written answer to a new situation, assessed by part like an exercise).
_Avoid_: Flashcard, a repeat of an exercise already seen (a chapter quiz asks earlier exercises again as such, not as new questions).

**Not studied**: A section before the learner's position, or before the section they return to, that has no lesson; worked out from lessons, never stored, and studiable at any time (ADR 0006).
_Avoid_: Skipped section (retired: passed-over sections are no longer marked), excluded, deferred item.

**Return section**: The section the learner comes back to after choosing to study another section out of route order, kept with the position as `return_to` until they go back to it or move past it (ADR 0006).
_Avoid_: Mainline restore point (where a side question returns to), bookmark, skipped section.

**Course library**: The learner's Throughline folder holding every course workspace; and the app view that lists courses for opening, with Studio at its top. From the list a course is only renamed, archived or deleted (ADR 0022); changes to what it teaches happen in Studio or a Codex chat.
_Avoid_: Course manager, a second store of progress, Studio (where courses are changed).

**Archived course**: A course left out of the library's list and the course switcher, shown under Archived courses, where it can still be opened. Archiving is recorded in the library's own folder and changes nothing in the course (ADR 0022).
_Avoid_: Finished, completed, closed, hidden forever.

**Course trash**: The library's `.throughline/trash/` folder, where a deleted course waits whole, with its progress, notes and questions, until it is restored. The app never empties it (ADR 0022).
_Avoid_: Recycle bin (the system's), permanent deletion, backups (copies kept before a format update).

**Course package**: One file holding a copy of a course at a share level, with its sources, to give to someone else or to move or back up one's own. Importing it makes a new course; nothing syncs back (ADR 0020).
_Avoid_: Course folder copy, template, sync.

**Share level**: How much of a course a package holds: Route (the route and sources), Route and lessons (adds lessons and exercises without the sender's answers) or Everything. The recipient takes at most that much when importing.
_Avoid_: Privacy setting, export format.

**Studio**: The place in the app where Codex works on the course with the `$throughline` skill: making a course from files, adding files, rebuilding the route, checking pages, changing how a course is taught, and making what the fast views cannot, such as sheets, mock exams or a problem set's exercises. It is the main line; content questions go to the teacher in Questions (ADR 0016, ADR 0026).
_Avoid_: Chat, workshop, side question, teaching.

**Suggested course change**: A change to the course itself that the teacher proposes under a lesson reply or side-question answer, which the learner opens in Studio with the request filled in or dismisses. One is open at a time (ADR 0016).
_Avoid_: Suggested preference (course memory), a Studio hand-off button, supplement (taught in the side question itself).

**Page reading**: Codex's transcription of one PDF page read as an image: its text with formulas and tables, its figures and what could not be read. A page with a reading is verified (ADR 0019).
_Avoid_: Extracted text (what pypdf returns), OCR, coverage (whether the page is taught).

**Figure**: A region of a source page that a lesson can show, recorded in the page reading by its box on the page, label, caption and description; the interface crops it from the page (ADR 0019).
_Avoid_: An extracted image file, an image from the web, a drawing the teacher writes (a teaching widget).

**Coverage ledger**: A list linking teaching content in the materials to concepts, source locations, and inclusion or deferral decisions; it does not establish learner mastery.
_Avoid_: Mastery, reading progress.

**Studio place**: The first of a course's three places, with Learn and Review, labelled Studio: Studio as tall as the window and, in a column beside it, the course (title, goal, chapter strip), its Studio threads and how the learner is taught (the confirmed preferences in course memory) (ADR 0017).
_Avoid_: Course page, Overview (both retired: the page had almost no overview and hid Studio), dashboard, chapter page, the side panel (used while reading a section).

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

**Attached image**: A picture the learner adds to an answer, a side question, a question about an exercise or a learner note, such as a photo of handwritten work. Those on answers and questions are sent to the teacher; those on notes stay private.
_Avoid_: Answer image (it is no longer only for answers), upload.

**Bookmark**: A learner annotation marking a section or a source location to come back to.
_Avoid_: Deferred item, mainline restore point.

**Course memory**: What the teacher keeps about one course: confirmed learner preferences (from teaching, or stated when the course was built or in Studio), taught terms and difficulties, each citing the interactions behind it. The learner sees and edits the confirmed preferences and can tell the teacher what to remember; taught terms and difficulties stay the teacher's working notes (ADR 0010).
_Avoid_: Learner profile (reported when the course was built), learner annotation, evidence, mastery, chat history.

**Taught term**: A term or notation recorded in course memory with the section, lesson step or side question that defined it; the teacher may use it without defining it again.
_Avoid_: Glossary of the materials, coverage ledger.

**Difficulty**: An idea the learner has repeatedly got wrong, recorded in course memory until a later check question or exercise on it is answered correctly.
_Avoid_: Needs-work assessment (one result), misconception label, weakness score.

**Teaching widget**: Part of a lesson's Markdown that the interface draws: LaTeX, highlighted code, a callout or a Mermaid diagram (the basics, always available), or an add-on (ADR 0013).
_Avoid_: Plugin, interactive simulation, embed.

**Cover**: What a course's card in the library shows above its title: the subject's short name, as a student would say it, over a pattern of thin lines. Codex chooses both (`cover.save`) and the app draws the pattern; a course without one shows its title over a pattern (ADR 0027).
_Avoid_: Thumbnail, icon, a picture of a source page, the course's title.

**Add-on**: A teaching widget for particular subjects, such as function plots or chemical equations, from the library in this repository. Codex selects a course's add-ons; only their guides enter the teacher's instructions, while the interface draws every add-on in every course. Learners never see or manage them.
_Avoid_: Plugin (third-party code), a Settings toggle, the basic widgets.
