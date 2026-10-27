# Exercises are assessed part by part

An assessment gave one outcome, `passed` or `needs_work`, for the whole exercise, and the interface showed only the latest one. Most generated and homework exercises have several parts, and the outcome did not fit them:

- A four-part exercise with three parts right was `needs_work` three times running, with no sign of what was already done.
- A learner answering one part at a time had the exercise `passed` after its first part, before the other parts were assessed.
- A learner who asked in the answer box what a part meant had that question assessed as `needs_work`, which reopened an exercise that had passed.

## Parts

An exercise lists its **exercise parts** (an exercise without subquestions has one). Each part's question is on its own line. An assessment gives each part the learner addressed one status: `correct`, `partly_correct` or `not_yet`; parts not addressed stay `not_attempted` and keep any earlier status. The exercise is solved once every part is `correct`; the interface shows progress as parts correct out of parts. Part statuses accumulate across submissions, so a learner can answer one part at a time.

Assistance stays per exercise: a solved exercise is `independent` only if no hint, key steps or solution was used on it, otherwise `hinted`, as before. `evidence.assess` keeps `outcome` (`passed` exactly when the exercise becomes solved, else `needs_work`) and adds the part statuses, so existing evidence, the review schedule and the chapter quiz (ADR 0008), which read `outcome`, stay valid. Review and quiz questions have parts like any exercise.

## Asking and skipping

- Asking what an exercise or part means is its own action. It is answered like a short side question and never assessed.
- Answers can include pasted or uploaded images of handwritten work, saved in the course workspace and sent to the teacher with the answer.
- Besides **Do later** (a deferral that returns at review), the learner can **skip** an exercise. A skipped exercise is closed: it is not open, not deferred, never reminded, and records no outcome. An optional reason (too easy, too tedious, not relevant) may lead the teacher to suggest a preference for course memory (ADR 0010), which the learner confirms. Skip applies to a section's exercises; review questions keep "Not now" and quiz questions can stay unanswered (ADR 0008). A chapter quiz never asks a skipped exercise again.
