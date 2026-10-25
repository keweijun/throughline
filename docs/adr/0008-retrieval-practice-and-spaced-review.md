# Retrieval practice and spaced review

Throughline's job is to help a learner learn a subject properly across sessions (ADR 0004). Until now nothing brought earlier material back: practice sat only at the end of each section, the chapter recap explicitly set no exercises, and a section passed once was never revisited. Retrieval practice (answering from memory) and spacing (returning to material at growing intervals) are the best-supported ways to make learning last, and the course already records the evidence a schedule needs.

## Review schedule

A section becomes reviewable once one of its exercises is assessed `passed` (independently or with help). Its review is due after an interval that grows with each successful review: 1, 3, 7, 21 and then 60 days after the last pass. A review passed without help moves to the next interval; one passed with help repeats the same interval; `needs_work` returns to the first interval. An ordinary exercise passed later restarts the wait at the same interval. The schedule is computed when read (`review.schedule`), from assessment evidence and its `assessed_at` time, so it needs no background job and stays correct after the host was closed for weeks. `evidence.assess` records `assessed_at`; migration 4 (ADR 0007) dates earlier app assessments by the start of the practice turn that produced them, and an assessment it cannot date reads as long ago.

## Review questions

- **Review** in the top bar shows how many sections are due and opens a review page. Due sections are listed oldest first, at most five a day counting reviews already answered that day, so a long break does not turn into a wall of work; the rest wait for later days. Before anything is reviewable the page says when sections become reviewable.
- **Start review** asks the teacher, through a practice job with `purpose: "review"`, for one fresh retrieval question for that section: recall its key idea and apply it to a new situation, without new material, hints in the question, or a repeat of an exercise the learner already saw (those questions are passed as data). It is a practice task with `origin: "review"` and uses the existing exercise interface: Check my answer, Hint, Key steps, Full solution. A started review stays listed until answered.
- Review questions live on the review page only: `/api/state` lists them under `review.tasks`, not among the section's exercises, so they never count as a section's open exercises. "Do later" is replaced by "Not now".
- Each practice task is its own assessment session (`practice:<task id>`), so a review is always another session. Its assessment is recorded through `evidence.assess` with `retest_of` set to the section's latest independent pass when there is one, so an unaided review pass becomes `retest_passed`.
- **Not now** (`review.postpone`) postpones a due section by one day. Reviews never gate the route: the learner can always move on, and sections skipped with their chapter (ADR 0006) are not scheduled until studied.

## Chapter quiz

The chapter page offers an optional chapter quiz, separate from the chapter recap (ADR 0006), which teaches and asks nothing. "Take the chapter quiz" is available once any section of the chapter has a completed lesson, wherever the learner is; it never moves the position and needs no recap first.

- **Composition.** Up to three earlier exercises from the chapter's sections, asked again, plus two or three new questions spanning the chapter. Earlier ones come from studied sections that are not skipped, never from review or quiz questions, and in this order: ones last assessed as solved with help or needing another try, then ones set aside ("Do later"), then ones solved independently. Exercises never answered nor set aside are still open and are not asked. The first pass takes at most one per section, so the quiz spreads across sections; remaining room goes to the next best. Among equals, an exercise asked in fewer earlier quizzes comes first.
- **Storage.** A practice job with `purpose: "chapter_quiz"` and `chapter_id` freezes the chosen exercises when it is created and asks the teacher for the new questions, passing the earlier ones so it does not duplicate them. On completion every question becomes a practice task with `origin: "chapter_quiz"`, `chapter_id`, `quiz_id` and `tests_concept_ids` (the earlier exercise's section, or the sections a new question spans). An earlier exercise is a new task with its question and sources copied and `from_task_id`; the original keeps its history. The anchor `concept_id` is the chapter's last section, as for the recap; quiz questions never count among that section's exercises.
- **Assessment.** A quiz question's help and assessment are recorded for the first section it tests, and when it tests one section with an earlier independent pass from another session, through `retest_of`, so an unaided pass is `retest_passed`. The review schedule treats each answer as a review of every section the question tests. A quiz question is not set aside; it can simply stay unanswered.
- **Retaking.** A new quiz waits until every question of the chapter's quizzes so far is answered (passed or needs work); then "Take the quiz again" makes a fresh quiz, and earlier quizzes stay listed with their results. The page shows the current quiz's progress.

Migration 5 (ADR 0007) moves earlier recap questions (`origin: "recap"`, created after a recap in the chapter's last section) to the chapter as `chapter_quiz` tasks, keeping their `tests_concept_ids`.

## Not chosen

- **Flashcards or a separate card deck.** STEM understanding is shown by applying an idea, which the existing exercise and assessment flow already handles; cards would duplicate it and test recall of wording.
- **A mastery gate.** Throughline deliberately never blocks the route (ADR 0006); reviews inform, they do not lock.
- **Scheduling from self-ratings.** Ratings like "easy/hard" are cheap but unreliable; the teacher's assessment of an actual answer is already recorded.
