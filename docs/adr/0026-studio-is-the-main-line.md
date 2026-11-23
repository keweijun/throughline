# Studio is the main line, and the fast views hand off to it

Throughline has two things a learner talks to:

- **The teacher in Learn and Review:** fast and scoped. It teaches, answers side questions, assesses and drills, but cannot touch files or sources or change the course.
- **Studio:** Codex itself (ADR 0016). It can do anything, but it is slower and has a place of its own, the first of the course's three (ADR 0017).

Both are a box you type into, and nothing shows how far apart they are. New users never find out what Studio can do, so the app reads as one more chat-based tutor, while Throughline's edge is that Codex works on the course (issue #229). The bridges we had were one-offs: suggested course changes prefilled in Studio, "in Studio" links, and a drill teacher saying "ask Studio".

## Decision

**Studio is the main line.** It is the agent: it builds and reshapes courses and does anything that needs files, sources or changes to the course. Learn and Review stay fast, structured views. Their boxes are not turned into agent views: a lesson or a drill cannot grow into an agent's workspace, and making every box one would blur both.

### One hand-off

What a fast view cannot do is **handed off** to Studio, always through the same path (`app.handOff`, `StudioHandoff`). The request goes out as a new Studio chat:

- **The message** is `$throughline <request>`. The request is written as the learner would ask, complete on its own.
- **The context note** says where the request came from (ADR 0016's `Context from Throughline: …`): the place, what it covers, and in a drill, the questions so far and how they went.
- **The record.** The course keeps the hand-off (`handoff.save`, namespace `studio_handoffs`) with where it was asked and the chat it started.

The learner stays where they were. The card that sent the request follows the chat: **Studio is working on it**, **Studio needs your answer**, or **Done in Studio**, each with **Open**. It keeps doing so after a reload: a card with no fixed id follows the latest hand-off of its request from its place. A hand-off always goes to the course's Studio, even when Studio was last open on the library. If the course cannot record a hand-off Studio has taken, the card says so and links to the chat.

**Consent.** With full access a hand-off runs in one click. Without it, the card asks once, beside it: Studio will work on the course in its own chat and may add files, exercises or sheets. Where Studio cannot run, the card says so and copies the request for a Codex chat.

Hand-offs today:

- **A drill's offer.** When the learner asks for something a drill cannot do, or it would clearly help, the fast teacher says so and ends its reply with `<studio-request>{"label", "request"}</studio-request>` (at most one per reply). The app shows it as a card under the reply (`drill.offer`). The teacher is told which offers were sent.
- **Studio ways in Review.** Beside the box: **Mock exam**, **Formula sheet** and **My mistakes on one page**, written for the scope.
- **The chapter page.** **One-page summary in Studio**, beside the heading of its key points.
- **A suggested course change** (ADR 0016) is now sent as a hand-off, not prefilled in Studio. It is answered once sent, and its card stays to follow the chat.

### Showing what Studio can do

- **First-entry card.** The first time a learner opens a course, once per learner (`studio-intro` among the seen hints), a card explains Studio. It says "Codex works on this course with you", gives three requests drawn from this course (a formula sheet for its first chapter, its source's problems as exercises, and a mock exam once something in that chapter is studied, else a one-page map of the course), each a hand-off, and recommends full access when it is off, unless the learner already chose Studio's access in the first-open series (ADR 0017).
- **In context, few.** Beyond that, Studio requests appear only where they fit, as above, not as buttons on every page (#134).

### Ways to review

The fast teacher runs more ways than quick questions. Each is a guide in its prompt (`prompts.DRILL_WAYS`) and a choice under **Other ways** in Review, not a page of its own. A session keeps its `way`.

- **Explain it back:** apply questions whose parts are what a complete explanation covers.
- **Oral quiz:** one short question at a time in the conversation.
- **Tell confusable ideas apart:** from course memory's difficulties, which the drill's review state now carries, and from open mistakes.

### What Studio makes comes back to Review

Studio works best from what the learner actually got wrong, and what it makes for review belongs where review happens. New skill operations make both possible, and they are part of the 1.0 promise (docs/stability.md):

- **Reading review data.** `mistakes.list`, `drill.list` and `review.context` (with an optional `sections`) join the skill. This lets Codex build a mock exam weighted to what the learner misses, or a page of their mistakes.
- **`drill.write`: a session Codex writes**, such as a mock exam from past papers, a problem set to answer from memory, or "drill me on this file".
  - **Questions:** review questions under the drill's rules, over a `scope` of studied sections. At most 30, with optional `marks`. `exam: true` shows them as a paper, with the total marks, and a `note` above them.
  - **Placement:** they lead the session in Review (`<id>:written:NN`, `origin: "studio"`). Answers count and misses reach the mistakes book, as in any drill, and the learner can carry the session on with the fast teacher.
  - **Errors:** an invalid question refuses the whole session, since Codex can correct it.
- **`sheet.save`: a sheet**, such as a cheat sheet, a formula sheet or the learner's mistakes on one page.
  - **Format:** Markdown with LaTeX, with a `scope` of chapters or sections.
  - **Where it shows:** under **Sheets**, a third tab in Review that appears when a sheet touches the scope, and as links on the chapter page of a chapter it covers. It can be printed alone (`body[data-print]`).
  - **Changes:** saving under the same id replaces it, which is how Codex changes it when asked. The learner can remove a sheet; Codex can write it again.
- **`handoff_id` on `drill.write`, `sheet.save` and `practice.add`.** A hand-off's context gives Codex its id, and Codex passes it when it saves what it made. The hand-off then records the result (`handoffs.record_result`), and the card that sent it reads **Done: <title> · Open it**: open the session, open the sheet, or go to the section given the exercises. A result saved before the app recorded its hand-off waits for it.

## Not chosen

- **An agent behind every box.** It is slower, every place would need an agent view, and the learner would still meet the agent's waiting and permissions everywhere.
- **Leaving Studio as a separate destination with links.** That is what we had: the gap stayed invisible until hit.
- **Jumping to Studio on every hand-off.** The learner is mid-study, so the card follows the chat instead and **Open** is one click away.
