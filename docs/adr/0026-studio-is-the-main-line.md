# Studio is the main line, and the fast views hand off to it

Throughline has two things a learner talks to:

- **The teacher in Learn and Review:** fast and scoped. It teaches, answers side questions, assesses and drills, but cannot touch files or sources or change the course.
- **Studio:** Codex itself (ADR 0016). It can do anything, but it is slower and sits on the Overview.

Both are a box you type into, and nothing shows how far apart they are. New users never find out what Studio can do, so the app reads as one more chat-based tutor, while Throughline's edge is that Codex works on the course (issue #229). The bridges we had were one-offs: suggested course changes prefilled in Studio, "in Studio" links, and a drill teacher saying "ask Studio".

## Decision

**Studio is the main line.** It is the agent: it builds and reshapes courses and does anything that needs files, sources or changes to the course. Learn and Review stay fast, structured views. Their boxes are not turned into agent views: a lesson or a drill cannot grow into an agent's workspace, and making every box one would blur both.

### One hand-off

What a fast view cannot do is **handed off** to Studio, always through the same path (`app.handOff`, `StudioHandoff`). The request goes out as a new Studio chat:

- **The message** is `$throughline <request>`. The request is written as the learner would ask, complete on its own.
- **The context note** says where the request came from (ADR 0016's `Context from Throughline: …`): the place, what it covers, and in a drill, the questions so far and how they went.
- **The record.** The course keeps the hand-off (`handoff.save`, namespace `studio_handoffs`) with where it was asked and the chat it started.

The learner stays where they were. The card that sent the request follows the chat: **Studio is working on it**, **Studio needs your answer**, or **Done in Studio**, each with **Open**. It keeps doing so after a reload.

**Consent.** With full access a hand-off runs in one click. Without it, the card asks once, beside it: Studio will work on the course in its own chat and may add files, exercises or sheets. Where Studio cannot run, the card says so and copies the request for a Codex chat.

Hand-offs today:

- **A drill's offer.** When the learner asks for something a drill cannot do, or it would clearly help, the fast teacher says so and ends its reply with `<studio-request>{"label", "request"}</studio-request>` (at most one per reply). The app shows it as a card under the reply (`drill.offer`). The teacher is told which offers were sent.
- **Studio ways in Review.** Beside the box: **Mock exam**, **Formula sheet** and **My mistakes on one page**, written for the scope.
- **The chapter page.** **One-page summary in Studio**, beside the heading of its key points.
- **A suggested course change** (ADR 0016) is now sent as a hand-off, not prefilled in Studio. It is answered once sent, and its card stays to follow the chat.

### Showing what Studio can do

- **First-entry card.** The first time a learner opens a course, once per learner (`studio-intro` among the seen hints), a card explains Studio. It says "Codex works on this course with you", gives three requests drawn from this course (a formula sheet for its first chapter, its source's problems as exercises, a mock exam), each a hand-off, and recommends full access when it is off.
- **In context, few.** Beyond that, Studio requests appear only where they fit, as above, not as buttons on every page (#134).

### Ways to review

The fast teacher runs more ways than quick questions. Each is a guide in its prompt (`prompts.DRILL_WAYS`) and a choice under **Other ways** in Review, not a page of its own. A session keeps its `way`.

- **Explain it back:** apply questions whose parts are what a complete explanation covers.
- **Oral quiz:** one short question at a time in the conversation.
- **Tell confusable ideas apart:** from course memory's difficulties, which the drill's review state now carries, and from open mistakes.

## Next

Studio writes what it makes back into Review (issue #229, step 2): `drill.write` for sessions and mock exams, and `sheet.save` for sheets. Studio also gets read access to review data, and the operations take a `handoff_id`, so a card's **Done** links to what was made.

## Not chosen

- **An agent behind every box.** It is slower, every place would need an agent view, and the learner would still meet the agent's waiting and permissions everywhere.
- **Leaving Studio as a separate destination with links.** That is what we had: the gap stayed invisible until hit.
- **Jumping to Studio on every hand-off.** The learner is mid-study, so the card follows the chat instead and **Open** is one click away.
