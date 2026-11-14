# Exercises and review sets

Use the same JSON entrypoint as [course operations](course-operations.md). The app's teacher writes a section's exercises and the review sets the learner asks for in the app. Use these operations when the learner asks you, in Studio or a Codex chat, to change what they practise in a course they are studying: put a problem set's questions in front of them, reword exercises (full text instead of a link, formulas in LaTeX, references added), remove duplicates, or review studied sections before an exam.

Never write streams, practice jobs or `practice.complete` yourself, and never use `practice.skip` for the learner: those belong to the app and its teacher, and a skip records that the learner closed the exercise.

## Read

- `{"op":"practice.list"}` returns `tasks` and `jobs`. A section exercise has `id`, `concept_id`, `question`, optional `parts`, `origin` (`source` for one of the course's exercises, which names it in `exercise`; `self_created` for one written for the section), `source_refs`, `status` and `history` (the learner's answers, asks and help, with the assessed part statuses). Statuses: `pending`, `attempted`, `deferred` (the learner chose Do later), `skipped` (the learner closed it), and two kept only for the record, never shown: `replaced` (the learner asked the teacher for different exercises) and `retired` (below). Review and chapter-quiz questions have `origin` `review` or `chapter_quiz`.
- `{"op":"review.sets"}` lists review sets; `{"op":"review.context"}` lists the studied sections a review may test, when each was last practised, recent misses and earlier review questions.

## Add exercises to a section

`{"op":"practice.add","id":"ps3-stack","concept_id":"stack","exercises":[{"question":"Problem 3: …","parts":["(a) …","(b) …"],"origin":"source","source_refs":[{"source_id":"src-…","revision":"…","unit_id":"page-4"}],"exercise":"3"}]}` adds exercises to one section as the learner will read them, and returns the `tasks` (ids `<id>:<index>`). Repeating a request with the same `id` returns the same exercises and adds nothing.

- Write each question in full, as the learner should see it: the source's text with its formulas in LaTeX and what it needs to be answered, not a link to the page. `parts` lists the subquestions, each as text or `{label, text}`; give one per subquestion, since each is assessed on its own.
- A course exercise has `origin: "source"`, a `source_refs` entry on its page and `exercise` naming one of the section's exercises in the curriculum (its `question`). Map it there first, in the latest section it needs ([exercise placement](curriculum.md#exercise-placement)): an exercise may not come before what it needs. One you write yourself has `origin: "self_created"`; its `source_refs`, if any, must be pages the section links.
- A course exercise already shown in the section is not added again (`exercise_exists`): revise it instead. A refused request adds nothing.

## Revise an exercise

`{"op":"practice.revise","id":"ps3-stack:0","question":"…","parts":[…],"source_refs":[…]}` changes the wording of an exercise still shown in a section, giving only the fields that change. The learner's answers, help and part statuses stay; earlier wordings are kept in `revisions`. Once an answer was assessed, the number of parts cannot change (`exercise_answered`), since the part statuses would no longer fit; keep the parts and reword them.

## Retire an exercise

`{"op":"practice.retire","id":"ps3-stack:2","reason":"Duplicate of problem 2"}` takes an exercise out of its section when the learner never touched it (a duplicate, one added by mistake). It is kept for the record and never shown, counted or asked again. An exercise the learner worked on cannot be retired (`exercise_answered`): revise it, or tell the learner they can skip it.

## Write a review set

When the learner asks to review what they studied (before an exam, a topic that feels shaky), write a review set rather than a document or a chapter: its misses then count for the sections each question tests and reach later reviews. `{"op":"review.write","id":"exam-1","request":"20 minutes before the 15 Nov test","scope":{"chapter_ids":["ch2"]},"questions":[…],"note":"…"}` saves the set with its questions in one step, and the app lists it on the review page at once.

- `request` says what the learner asked for; `scope` (`chapter_ids`, `concept_ids`) is optional. A set may test only studied sections (`nothing_to_review` when none matches); read `review.context` first. Reviewing unstudied material is teaching: say in `note` what you left out and why, which the page shows with the set.
- Each question names the sections it tests in `tests_concept_ids`, and usually connects more than one. An **apply** question (`"kind":"apply"`, the default) is answered in writing and assessed by part like an exercise: `{"kind":"apply","question":"…","parts"?:[…],"tests_concept_ids":["stack"]}`. A **recall** question is multiple choice with instant feedback: `{"kind":"recall","question":"…","idea":"…","options":[{"text":"…","explanation":"…"}],"correct":0,"tests_concept_ids":["stack"]}`, with 2 to 5 options, each explained. At most 8 questions; any invalid question rejects the whole set (`invalid_review_question`).
- To practise sections not studied yet, add exercises to them instead.

## Plans for a deadline

The learner studies any section from its preview in the app, earlier or later, and sections passed over show as not studied: nothing needs to be removed or marked to leave sections out. For a plan such as "300 minutes before the exam, leave out perturbation theory", tell the learner which sections the plan covers, in order, and record how they want to be taught meanwhile as a preference (`memory.save`, `memory.confirm`) that says when it ends ("until the exam on 15 Nov"), so they can delete it afterwards. Reordering the route still needs their agreement.
