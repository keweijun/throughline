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

## Review before an exam

Review happens in the app's **Review** place, not in a document or a chapter you write. There the learner reads the key points of what they studied, goes over their mistakes book, and drills with a fast teacher whose questions count for the sections they test. The learner can narrow it to chapters or sections first. When the learner asks you to review ("20 minutes before tomorrow's test"), open the course and tell them where: Review, choose the chapters, then Drill me, saying what to focus on. To add a problem set's questions for them to practise, add exercises to their sections (above). A cheat sheet or summary they asked for is a file you write for them; it is not course material.

## Key points

The app's teacher writes every studied section's key points: the results, rules and methods to hold from it, each with when it holds and a common mistake. The learner reads them at the end of the lesson, at the top of the section and on the chapter's sheet, but cannot edit them; they ask you instead ("say it without the matrix notation", "add the sign convention", "this one is wrong").

- `{"op":"key_points.view","concept_id":"stack"}` returns the section's `key_points`: `points`, each `{statement, holds_when?, common_mistake?, turn_id?, source_refs}`, and `requests`, the changes the learner asked for before. Without `concept_id` it lists every section's points and the chapter sheets.
- `{"op":"key_points.revise","concept_id":"stack","request":"Add the sign convention","points":[…]}` replaces the section's points. Give every point the section keeps, not only the changed one, and copy each kept point's `turn_id` and `source_refs` so it still links to the lesson step and pages that taught it; `source_refs` may only name pages the section links. `request` says what the learner asked for, in their words: when a later lesson rewrites the points, the teacher keeps that change unless the lesson contradicts it. Points are Markdown with LaTeX, at most 12 per section, and only a section with a completed lesson has them (`not_studied`).

## Plans for a deadline

The learner studies any section from its preview in the app, earlier or later, and sections passed over show as not studied: nothing needs to be removed or marked to leave sections out. For a plan such as "300 minutes before the exam, leave out perturbation theory", tell the learner which sections the plan covers, in order, and record how they want to be taught meanwhile as a preference (`memory.save`, `memory.confirm`) that says when it ends ("until the exam on 15 Nov"), so they can delete it afterwards. Reordering the route still needs their agreement.
