# Exercises are assessed part by part

An assessment gave one outcome, `passed` or `needs_work`, for the whole exercise, and the interface showed only the latest one. Most generated and homework exercises have several parts, and the outcome did not fit them:

- A four-part exercise with three parts right was `needs_work` three times running, with no sign of what was already done.
- A learner answering one part at a time had the exercise `passed` after its first part, before the other parts were assessed.
- A learner who asked in the answer box what a part meant had that question assessed as `needs_work`, which reopened an exercise that had passed.

## Parts

An exercise lists its **exercise parts** (an exercise without subquestions has one). Each part's question is on its own line, and a part may carry a short label such as "(a)", which the interface shows instead of "Part 1". An assessment gives each part the learner addressed one status: `correct`, `partly_correct` or `not_yet`; parts not addressed stay `not_attempted` and keep any earlier status. The exercise is solved once every part is `correct`; the interface shows progress as parts correct out of parts. Part statuses accumulate across submissions, so a learner can answer one part at a time.

Assistance stays per exercise: a solved exercise is `independent` only if no hint, key steps or solution was used on it, otherwise `hinted`, as before. Assessment feedback counts as help only when it marks an answered part `partly_correct` or `not_yet`, since it may then reveal a method or answer; feedback that only confirms correct parts is no help, so a learner answering part by part can still solve an exercise independently. `evidence.assess` keeps `outcome` (`passed` exactly when the exercise becomes solved, else `needs_work`) and adds the part statuses, so existing evidence and the chapter quiz (ADR 0008), which read `outcome`, stay valid. The review schedule also reads the part statuses: a review assessment that finds only correct and unanswered parts is neither a pass nor a miss (ADR 0008). Review and quiz questions have parts like any exercise.

## Asking and skipping

- Asking what an exercise or part means is its own action. It is answered like a short side question and never assessed.
- Answers can include pasted or uploaded images of handwritten work, saved in the course workspace and sent to the teacher with the answer.
- Besides **Do later** (a deferral; set-aside exercises enter the review context, ADR 0014), the learner can **skip** an exercise. A skipped exercise is closed: it is not open, not deferred, never reminded, and records no outcome. An optional reason (too easy, too tedious, not relevant) is remembered: once two exercises in a course are skipped with the same reason, the host suggests a matching preference for course memory (ADR 0010) in fixed wording, citing those skips, which the learner confirms or dismisses. It is not suggested again once dismissed or while a matching preference exists. Skip applies to a section's exercises; review and quiz questions can simply stay unanswered (ADR 0014). A chapter quiz never asks a skipped exercise again.

## Different exercises

Exercises written for a section may not suit the learner (too much arithmetic, a setting that does not interest them), and once they were ready the only way out was to skip them one by one.

- **Ask for different exercises**, under a section's practice, with an optional note ("easier to set up", "more on the boundary conditions", "less arithmetic"), asks the teacher for a new set. It replaces the section's exercises the teacher wrote (`origin: "self_created"`) that the learner has not touched: no answer, ask, hint, steps or solution. Replaced exercises get status `replaced` and are kept for the record but no longer shown or counted. The course's own exercises (`origin: "source"`, homework and problem sets) are never replaced; they can be skipped.
- **Another like this**, on one exercise, asks for one more exercise of the same kind next to it, without replacing anything.
- New exercises must still meet the section's objective: the note changes how a problem is posed, not what solving it shows. The teacher sees the replaced exercises, so it does not write them again.
- A request with a note carries a memory note (ADR 0010): when the note says how the learner wants to practise, the teacher may suggest it as a preference, which the learner confirms as usual.
