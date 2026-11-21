# Exercises, key points and review

Use the same JSON entrypoint as [course operations](course-operations.md). The app's teacher writes a section's exercises, its key points and the questions of a review. Use these operations when the learner asks you, in Studio or a Codex chat, to change what they practise in a course they are studying: put a problem set's questions in front of them, reword exercises (full text instead of a link, formulas in LaTeX, references added), remove duplicates, or change a section's key points.

Never write streams, practice jobs or `practice.complete` yourself, and never use `practice.skip` for the learner: those belong to the app and its teacher, and a skip records that the learner closed the exercise.

## Read

- `{"op":"practice.list"}` returns `tasks` and `jobs`. A section exercise has `id`, `concept_id`, `question`, optional `parts`, `origin` (`source` for one of the course's exercises, which names it in `exercise`; `self_created` for one written for the section), `source_refs`, `status` and `history` (the learner's answers, asks and help, with the assessed part statuses). Statuses: `pending`, `attempted`, `deferred` (the learner chose Do later), `skipped` (the learner closed it), and two kept only for the record, never shown: `replaced` (the learner asked the teacher for different exercises) and `retired` (below). Review and chapter-quiz questions have `origin` `review` or `chapter_quiz`.

## Add exercises to a section

`{"op":"practice.add","id":"ps3-stack","concept_id":"stack","exercises":[{"question":"Problem 3: …","parts":["(a) …","(b) …"],"origin":"source","source_refs":[{"source_id":"src-…","revision":"…","unit_id":"page-4"}],"exercise":"3"}]}` adds exercises to one section as the learner will read them, and returns the `tasks` (ids `<id>:<index>`). Repeating a request with the same `id` returns the same exercises and adds nothing.

- Write each question in full, as the learner should see it: the source's text with its formulas in LaTeX and what it needs to be answered, not a link to the page. `parts` lists the subquestions, each as text or `{label, text}`; give one per subquestion, since each is assessed on its own.
- A course exercise has `origin: "source"`, a `source_refs` entry on its page and `exercise` naming one of the section's exercises in the curriculum (its `question`). Map it there first, in the latest section it needs ([exercise placement](curriculum.md#exercise-placement)): an exercise may not come before what it needs. One you write yourself has `origin: "self_created"`; its `source_refs`, if any, must be pages the section links.
- A course exercise already shown in the section is not added again (`exercise_exists`): revise it instead. A refused request adds nothing.

## Revise an exercise

`{"op":"practice.revise","id":"ps3-stack:0","question":"…","parts":[…],"source_refs":[…]}` changes the wording of an exercise still shown in a section, giving only the fields that change. The learner's answers, help and part statuses stay; earlier wordings are kept in `revisions`. Once an answer was assessed, the number of parts cannot change (`exercise_answered`), since the part statuses would no longer fit; keep the parts and reword them.

## Retire an exercise

`{"op":"practice.retire","id":"ps3-stack:2","reason":"Duplicate of problem 2"}` takes an exercise out of its section when the learner never touched it (a duplicate, one added by mistake). It is kept for the record and never shown, counted or asked again. An exercise the learner worked on cannot be retired (`exercise_answered`): revise it, or tell the learner they can skip it.

## Review

Review happens in the app's **Review** place. The learner reads the key points of what they studied, goes over their mistakes book, drills with a fast teacher, and finds what you made for them. They can narrow it to chapters or sections first. What you make for review goes there too, not into a document or a chapter you add.

### What the learner got wrong and has practised

- `{"op":"mistakes.list"}` returns `entries`, newest first. Each entry is one miss:
  - `kind`: `exercise`, `quiz`, `review` or `check`.
  - `concept_ids`: the sections it tests.
  - The question, with its `part` when the miss was on one part.
  - What the learner answered (`answer`, or `chosen` for multiple choice) and the `feedback` or `why`.
  - `right_at`: when they later got it right, or null.
- `{"op":"review.context","sections":["stack"]}` returns, for each studied section (all of them without `sections`), the `days_since_practised`, `recent_misses` and `set_aside` exercises. It also returns `earlier` review questions with their outcomes.
- `{"op":"drill.list"}` returns the drill `sessions`, with their `sections` and `task_ids`. Their questions are in `practice.list` with `origin: "review"` and a `session_id`.

Build on these when the learner asks for review: a mock exam weighted to what they miss, a page of their mistakes.

### A session to answer in Review

`{"op":"drill.write","id":"mock-ch2","title":"Mock exam: chapter 2","scope":{"chapter_ids":["ch2"]},"exam":true,"note":"…","questions":[…]}` saves a session the learner answers in Review. Use it for a mock exam from past papers, a problem set to answer from memory, or "drill me on this file". Each answer counts for the sections its question tests, and a miss reaches the mistakes book. The learner can then ask the fast teacher for more in the same session.

- **Questions.** Each one names the sections it tests in `tests_concept_ids`, all of them studied and inside `scope` (all studied sections without a scope; `nothing_to_review` when none is studied).
  - **Apply** (`"kind":"apply"`, the default) is written and assessed by part: `{"question":"…","parts"?:[…],"tests_concept_ids":["stack"],"marks"?:6}`.
  - **Recall** is multiple choice: `{"kind":"recall","question":"…","idea":"…","options":[{"text":"…","explanation":"…"}],"correct":0,"tests_concept_ids":["stack"]}`, with 2 to 5 options, each explained.
- **Limits.** At most 30 questions. Any invalid question rejects the whole session (`invalid_review_question`).
- **Exam papers.** `exam: true` shows the session as a paper, in order, with each question's `marks`.
- **`note`** says what the session covers or leaves out, and the app shows it above the questions.
- **Replays.** Repeating the same `id` returns the session as it was.

### A sheet

`{"op":"sheet.save","id":"formulas-ch2","title":"Formula sheet: chapter 2","scope":{"chapter_ids":["ch2"]},"markdown":"…"}` saves a page the learner reads in Review and on the chapter page, and can print: a cheat sheet, a formula sheet, their mistakes on one page, a comparison table.

- **Content.** Write it in Markdown with LaTeX, as lessons are, and make it fit for printing on one or two pages.
- **Scope** names the chapters or sections it covers; leave it out for the whole course.
- **Changes.** Saving again with the same `id` replaces the sheet; use that when the learner asks you to change it.
- **Listing.** `{"op":"sheet.list"}` lists the sheets.

### Requests from the app

A request handed off from the app has a context naming where it was asked, ending `· hand-off <id>`. Pass that id as `handoff_id` to `drill.write`, `sheet.save` or `practice.add` when you save what you made: the card the learner pressed then links to it.

When the learner asks you to review ("20 minutes before tomorrow's test"), you can offer what fits:
- a mock exam (`drill.write`);
- a sheet (`sheet.save`);
- their problem set as exercises (above).

You can also tell them where to drill in Review: choose the chapters, then press Drill me.

## Key points

The app's teacher writes every studied section's key points: the results, rules and methods to hold from it, each with when it holds and a common mistake. The learner reads them at the end of the lesson, at the top of the section and on the chapter's sheet, but cannot edit them; they ask you instead ("say it without the matrix notation", "add the sign convention", "this one is wrong").

- `{"op":"key_points.view","concept_id":"stack"}` returns the section's `key_points`: `points`, each `{statement, holds_when?, common_mistake?, turn_id?, source_refs}`, and `requests`, the changes the learner asked for before. Without `concept_id` it lists every section's points and the chapter sheets.
- `{"op":"key_points.revise","concept_id":"stack","request":"Add the sign convention","points":[…]}` replaces the section's points. Give every point the section keeps, not only the changed one, and copy each kept point's `turn_id` and `source_refs` so it still links to the lesson step and pages that taught it; `source_refs` may only name pages the section links. `request` says what the learner asked for, in their words: when a later lesson rewrites the points, the teacher keeps that change unless the lesson contradicts it. Points are Markdown with LaTeX, at most 12 per section, and only a section with a completed lesson has them (`not_studied`).

## Plans for a deadline

The learner studies any section from its preview in the app, earlier or later, and sections passed over show as not studied: nothing needs to be removed or marked to leave sections out. For a plan such as "300 minutes before the exam, leave out perturbation theory", tell the learner which sections the plan covers, in order, and record how they want to be taught meanwhile as a preference (`memory.save`, `memory.confirm`) that says when it ends ("until the exam on 15 Nov"), so they can delete it afterwards. Reordering the route still needs their agreement.
