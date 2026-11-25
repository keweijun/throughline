# A section can get a new lesson

A section is taught once. After its stepped lesson (ADR 0009), the learner's only way back to the teacher is **Teach again**: one reply added below the lesson, written to resume it ("This section already has a lesson…"), with no plan, no steps and no checks. That fits a small request (another example, a longer derivation). It cannot carry what a section has gained since it was taught, and nothing else can.

A test user's course on a 460-page probability textbook shows what that costs. The first build gave its sections no plan and linked only the first pages of each, so its lessons stopped a few pages into ten- to fourteen-page sections. When the learner noticed, Studio audited the course and revised the sections as the skill says to ("chapters the learner has studied"). Then it had no way to have them taught:

- It wrote 14 single-page "supplement" lessons itself. They were poor, so it withdrew them. A section cannot be removed, so they sit in a chapter titled "withdrawn, do not study" at the end of the route.
- It added 23 new "补学" sections. A new section is the only thing that gets a fresh stepped lesson. They re-taught what the original sections had already taught. For example, a section's normal-distribution steps were taught again an hour later by a rebuild section. They also used ideas from later chapters, which the learner had studied but the route order had not reached.
- It registered its own teaching brief as a course source to carry those sections' plans. Lessons cite the brief, and the learner sees it among the textbooks.
- When the learner wanted to move on from an unfinished rebuild lesson, Studio wrote a fake final step saying the section had been "marked complete manually". The reason is that an open stepped lesson leaves a section unstudied.

None of this needed a new course operation. A section that has already been taught needed a way to be taught again.

## Decision

On a section that has a lesson, finished or not, the lesson request offers two kinds of request:

- **New lesson**: a stepped lesson, planned again from the section as it now stands: its core question, overview, links, notation and exercises, as a first lesson is. The learner's request, when given, focuses it ("only what the first lesson skipped", "more rigorously", "with the proofs"). The teacher receives the earlier lessons' step titles as data, marked as taught before. So a request to cover only what is missing can be met, and a full lesson can say where it goes over familiar ground. Without a request, the new lesson teaches the whole section. Checks, repairs, prepared steps and the step cap work as in any stepped lesson.
- **Another pass**: today's Teach again, one reply added to the lesson that is there. It is for a small, specific request.

New lesson also restarts a lesson the learner has not finished: the steps they read stay, and the rest of that lesson's plan is dropped. Regenerating one step, which ADR 0009 already allows, is a different thing: it keeps the lesson and writes that step again.

A New lesson replaces the section's lesson, so a section always has one current lesson. The replaced lesson is not deleted. It stays as it was, unfinished or not, with its check answers, annotations and side questions, shown folded above the new one and marked as replaced. Only the current lesson is continued, prepared ahead or shared. A section stays studied once any of its lessons has finished. An unfinished new lesson shows its step progress, but the section does not go back to unstudied. Practice is unchanged: the section's exercises stay, and the new lesson ends the way a lesson ends now.

When a learner asks Studio to fix a section they have studied, Codex revises that section and tells the learner to open it and choose New lesson. It does not add a section to get a lesson taught, and it never writes lessons itself (ADR 0004). A new section is still right for a new core question, as the skill already says.

### Replaced lessons in a shared course

A course package (ADR 0020) below Everything leaves replaced lessons out, as it already leaves out exercises the learner asked to replace. A recipient's section therefore has one lesson, revealed from its first step by Start and Continue as now, and there is no choice to make on import. A continued course keeps every lesson, the replaced ones included.

## Consequences

- A section can have several stepped lessons. `lesson.begin` already allows this. The host has to stop treating "has a taught turn" as "continue the lesson": only the explicit choice opens a new one. A lesson gains a replaced mark, and "studied" moves from the open lesson to whether any lesson is finished.
- The skill's [chapters the learner has studied](../../throughline/skill/references/curriculum.md#chapters-the-learner-has-studied) changes from "Study this, then come back" to choosing New lesson, alongside study-out-of-route-order where the section is ahead of the learner.
- An unfinished lesson no longer needs to be "completed" to move on: New lesson replaces its remaining plan, and the route already lets the learner study any section.
- ADR 0020: a package below Everything leaves replaced lessons out.
- This does not fix a bad build. Sections sized to a sitting, pages read and problems mapped are what keep the audit from being needed. A new lesson is how a course that was built badly, or whose sources changed, gets taught properly afterwards.
