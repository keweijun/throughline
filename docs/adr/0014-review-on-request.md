# Review on request

ADR 0008 brought earlier material back with a fixed schedule: each section that had a passed exercise came due after 1, 3, 7, 21 and 60 days, the review page listed due sections, and **Review** in the top bar counted them. In use it worked against itself:

- The page listed sections, not questions. After a few days away it showed a column of sections, which read as a backlog to clear rather than a few minutes of practice.
- The schedule could not be adjusted. Due counts, a daily cap and "Not now" made review feel mandatory, while the learner had no way to say *what* they wanted to review (before an exam, a topic that felt shaky).
- One question per section tested one idea of the section, yet moved the whole section's interval, and a single `partly_correct` part sent a long interval back to one day.
- Every review waited for a question to be written, then for a written answer to be assessed.
- The question was written from the section's title, core question and objective only, with none of what was taught, the course memory, or earlier reviews.
- A section whose exercises were skipped never became reviewable at all.

Spacing and retrieval practice remain the reasons to review (ADR 0008). What changes is who decides when: the learner asks, and the timing information becomes context for the teacher instead of a schedule. Learners judge poorly what they have forgotten, since material that feels familiar seems known, so the default request lets the teacher choose using that context, rather than leaving the learner to pick.

## Review sets

A **review set** is a group of questions written for one request. The review page lists sets, never sections: current sets first with their progress, then earlier sets, folded, with their results. A set stays current until the learner closes it (**Done**, or **Done for now** with questions unanswered) or, once every question is answered, for a day, so the feedback on its last answer can be read. Nothing is listed until the learner asks.

- **Review for me** asks with no request; the teacher chooses what to review from the review context.
- A **review request** is free text ("the variational method, not the derivations", "chapter 3 before my exam"), optionally with a scope of chapters or sections ticked from the route.
- A set may test only **studied sections** (a completed lesson or any learning evidence, not skipped; as for the chapter quiz in ADR 0008). Reviewing unstudied material is teaching, not review: when a request reaches beyond studied sections the teacher limits the set and says what it left out, in a short note the page shows with the set.
- The teacher decides how many questions a set has and of which kinds; the host enforces only a sanity cap.

Each question names the sections it tests (`tests_concept_ids`), and so does each part of a multi-part question, so a question can and usually should connect ideas from different sections while a miss still points at the section behind it. A question is one of two kinds:

- **Recall**: a multiple-choice or short-answer question written together with its answer and an explanation for every option, like a check question (ADR 0009), so feedback is instant and needs no model turn. A recall answer is recorded as an interaction (`kind: "review_answer"`) and enters the review context, but it is not learning evidence: a guessed choice says too little.
- **Apply**: a written question answered from memory and assessed part by part (ADR 0011) through the exercise interface: Check my answer, Hint, Key steps, Full solution. Its assessment is evidence for the first section it tests, with `retest_of` set as before, so an unaided pass is `retest_passed`.

Review questions stay on the review page: they never count among a section's open exercises. A question can simply stay unanswered; a set is finished when every question is answered or the learner closes it.

## Review context

Every review request carries the review context, computed when read, as data for the teacher:

- for each studied section: when it was last practised (the latest lesson, assessment or review answer on it), recent misses on it (assessed parts `partly_correct` or `not_yet`, and wrong recall answers), and its exercises set aside with **Do later**;
- course memory: difficulties and taught terms (ADR 0010);
- earlier review questions with their outcomes, so a set does not repeat them;
- source excerpts and the lesson plan of the sections in scope, so questions follow what was taught.

The teacher is asked to prefer sections that are stale or were missed, and to ask again, in a new situation, about what was missed before. No interval or due date is stored.

## Prepared set

So that **Review for me** opens at once, the host writes one set in the background when the course is open, the host is idle (nothing running, and nothing for preparation of the next section to do), some section is studied, the learner has asked for a review in this course before, and no prepared set is waiting. Learners who never review spend no teacher turns on it. It starts only when idle and runs beside any request made after it. It stays hidden until the learner asks for a review without a request, then becomes an ordinary set; one whose writing failed is closed and replaced then, so a failing teacher is never retried in a loop. A request with text or a scope always writes a new set.

## Warm-up

When the learner opens a section whose lesson has not started and a studied prerequisite of it (curriculum `prerequisites`) has not been practised for about a week, the section page offers **Warm up on what this builds on**: a small review set scoped to those prerequisites, preferring recall questions. It is offered once per section, dismissed with one click, and never gates the lesson.

## After a miss

A missed apply part or a wrong recall answer offers **Revisit**, a side question about that idea with the review question as its passage, answered route-aware like any side question. Misses are review context for later sets, and the assessment's memory note may record a difficulty as for any exercise (ADR 0010).

## Chapter quiz

The chapter quiz becomes a review set scoped to the chapter, whose id is the quiz's; its questions keep `origin: "chapter_quiz"` and name the set in `set_id`. **Take the chapter quiz** on the chapter page creates it, with the composition ADR 0008 defined (earlier exercises asked again, then new questions spanning the chapter's studied sections) and the rule that a new quiz waits until the questions of the last one are answered. It is listed on the chapter page and on the review page.

## What goes

The schedule (`review.schedule` intervals, due sections, the daily cap), "Not now" (`review.postpone` and `review_postponements`), the count on **Review** in the top bar, and the `daily_reviews` preference with its Settings row. **Review** stays in the top bar as a plain entry (hidden on phone-width screens, where it used to show only when something was due). **Do later** remains a deferral: set-aside exercises are listed on their section and chapter pages, enter the review context, and are asked again by chapter quizzes.

A migration (ADR 0007) turns existing review questions into review sets (one set per day they were started), turns each chapter quiz into a set scoped to its chapter keeping its `quiz_id`, and drops postponements and `daily_reviews`. Evidence is untouched.

## Not chosen

- **Keeping a schedule without the badge.** Due dates still imply a backlog; what the learner wanted was to decide when to review, with help deciding what.
- **Pure on-demand review without context.** It drifts toward what already feels familiar; the review context and **Review for me** counter that.
- **Storing key ideas per section and scheduling each.** Questions across sections, with sections named per part, attribute misses well enough without a new part of the course plan.
- **Self-ratings.** As in ADR 0008, the teacher's assessment of an actual answer is the evidence; a rating adds little.
