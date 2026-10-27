# Lessons are taught in steps with check questions

A section's first lesson used to be one long reply followed by grouped practice. In a real course (a physical chemistry course, 13 sections) these replies ran 3,000–6,000 characters and covered up to ten subtopics. Most of the learner's side questions were "what is X?" about a term or step the lesson had skipped, and nothing in the lesson noticed the gap before the next idea built on it. The same course's first lessons, taught in Codex chat in steps of about 1,500 characters that each ended with a short question, had none of these leaps.

We teach a section's lesson as a short sequence of **lesson steps**:

- Preparation plans the steps from the section's core question; the section overview's `steps` already name them. The teacher decides how many steps the section needs (a short or simple section may be a single step); the host only caps the plan at a sanity limit. A step is one turn of the mainline lesson and keeps the lesson lifecycle: it streams, can be paused, and is regenerated as a new attempt.
- A step may end with one **check question**, when the teacher judges that a quick question would catch a likely gap at that point: multiple choice, with options written around likely misconceptions and an "I'm not sure" option. The step's turn returns the question with the correct option and a one-line explanation for every option, so the learner sees feedback at once without another model turn.
- A correct answer leads to the next step. A wrong or "not sure" answer shows that option's explanation and the correct answer with its own, and the next step opens with a short fix aimed at that misconception before going on. Repairs never cost an extra turn.
- The learner may continue without answering. The check is then left unanswered and nothing is repaired.
- The teacher may adapt the plan freely while teaching: add a bridge step, reorder or merge the remaining steps. It may only use material that belongs to the section or its taught prerequisites; content of later sections stays with them (ADR 0006). The interface shows the step position and any added step.
- Grouped practice still ends the section. Check questions are not exercises.

## Check questions are not evidence

A check answer is recorded as an interaction, never through `evidence.assess`, and does not change a section's practice or evidence status. Multiple choice with the answer generated in advance cannot show independent work. Repeated misses on one idea become a difficulty in course memory (ADR 0010), which is how they reach later teaching. Checks are also not retrieval practice: they do not make a section reviewable or count as a review (ADR 0008), which still comes from assessed exercises.

## Consequences

- A lesson takes several turns, so the learner waits between steps. Preparation may draft the first step ahead; later steps depend on the learner's answers and are generated when needed.
- Lessons saved before this change stay single replies and are shown as they are.
