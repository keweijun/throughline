# Drill sessions replace review sets

ADR 0014 made review something the learner asks for: a **review set** of questions written for each request. In real courses it was barely used. Across four courses, one used review: 5 sets, 21 questions, 3 answers, and every set was left open. A set read as a task to finish, and each one took a full teacher turn to write before anything could be answered. Meanwhile learners reviewed in Studio, because there they could talk to an agent, steer it and ask for anything.

The Review place (ADR 0014, issue #219) now offers key points (ADR 0024) and a mistakes book over one scope. This ADR replaces its third way of reviewing: questions.

## Decision

A **drill session** is a conversation with a **fast teacher** over the Review place's scope. The learner presses **Drill me**, or says what to drill, and the teacher replies briefly with a few questions. The learner answers them in place, then asks for **More questions**, asks about an answer, or says what to drill next. A session is never finished, closed or due. There is no Done button and no progress count. It is kept, listed under **Earlier sessions** by date and scope, and can be reopened and continued.

### The fast teacher

- **Model.** Each turn runs on the small model, and so does the assessment of a written answer to a drill question. The small model is GPT-6.1 Terra unless the learner chose another in Settings: real runs found it two to three times faster than Sol at comparable quality (PR #231). Without a small-model effort set, the fast teacher runs at low effort. A drill is a quick back-and-forth, and a full teacher turn for every reply would be too slow. Under the trust-the-model stance, the small model's assessment counts as evidence.
- **Prompt.** It is lean and its own (`prompts.drill_instructions`): the teacher's rules, the drill rules, and the key points of every section in scope lead it as the thread's instructions, which stay the same through the session. After them comes the review state:
  - each section's review context (ADR 0014);
  - the open mistakes in scope;
  - the earlier review questions and how they went;
  - the session so far: what the learner said, what the teacher replied, and how each question went.
- **What it asks.** The teacher chooses unless the learner says what they want. It prefers ideas in open mistakes, asked again in a new situation; then sections not practised for longest; and now and then an earlier exercise asked again. It decides how many questions a reply sets, usually one to three; the host enforces only the review set's sanity cap (8).
- **Reply format.** A reply is short text followed by one `<drill-questions>` block. Its questions use the review question schema (ADR 0014):
  - **recall** questions: multiple choice, with every option explained and instant feedback;
  - **apply** questions: written, assessed by part.

  Every question names the sections it tests, all within the scope. An invalid recall question is dropped; any other invalid question drops that reply's questions, and the text stays.
- **Requests it cannot handle.** Asked for something it cannot do here, such as a file, a cheat sheet or collecting a problem set into the course, the teacher says Studio can, and what to ask there. Handing the request to Studio with one click is planned for after 1.0 (issue #219).

### Questions are review questions

A drill's questions are stored as practice tasks with `origin: review`, the `session_id` and the `drill_turn_id` that asked them, recorded for the first section they test. So everything ADR 0014 built for review questions applies unchanged:

- recall answers go through `review.answer` and are not evidence;
- written answers are assessed by part, and an unaided pass is a `retest_passed` of the section;
- misses reach the mistakes book, and a wrong recall answer offers **Revisit**;
- questions are never a section's exercises and cannot be skipped.

### What becomes a session

- **The chapter quiz** becomes **Drill this chapter** on the chapter page. It is a session of kind `chapter` scoped to the chapter, which opens in the Review place. Its rules begin it with one or two of the chapter's earlier exercises asked again, as the quiz did, then new questions spanning the chapter. Quizzes taken before stay on the chapter page, where unanswered questions can still be answered.
- **The warm-up** is a session of kind `warm_up`, scoped to the stale prerequisites of the section about to be learned. It is offered as before, once per section, and runs inline on the section page with two or three recall questions.
- **Test me on this** under a key point, and **Try it again** under a mistake, start a session in that section with the request as the learner's first message.

### What goes

- **Asking for review sets.** `POST /api/review/sets` and closing a set are gone. Sets written before stay readable, folded under **Review sets from before**, and their unanswered questions can still be answered.
- **The prepared set**, and the idle work that wrote it.
- **Taking a chapter quiz**: `POST /api/chapters/{id}/quiz` is gone.
- **The skill's review operations.** `review.write`, `review.sets` and `review.context` leave its references before 1.0, so they were never promised (docs/stability.md). `review.write` is removed. `review.sets` and `review.context` stay as internal operations the host reads. When the learner asks Codex to review, Codex sends them to the Review place. It adds a problem set's questions as exercises, and a cheat sheet is a file it writes for them.

Nothing stored changes shape: sessions are a new namespace (`drill_sessions`), carried only by Everything packages, and old sets and quizzes stay as they were. No migration is needed.

## Not chosen

- **Keeping review sets alongside sessions.** Two ways to ask for questions would split the review context and keep the "set to finish" that went unused.
- **A Studio agent for every turn.** Studio is what learners used, but a turn takes too long for a drill. Handing over to Studio covers what the fast teacher cannot do.
- **Writing the next questions ahead, like the prepared set.** On the small model a turn is quick, and questions written ahead could not take the learner's last answer into account.
