# Key points replace the chapter recap

Learners need something to come back to after a lesson: a page that says what to hold from each section, to read again before an exam or when a later section builds on it. The chapter recap (ADR 0006) was meant to be that, but in real courses it was started once. It was a lesson the learner had to ask for, written afresh each time, and it gave a chain of reasoning to read through, not a reference. Learners built their own reference instead, by highlighting.

Review is being reworked as well, around a Review place that offers several ways of reviewing over one scope (issue #219). Key points are the first of those ways, and the Review place will open on them, so they come first.

## Decision

The teacher writes **key points** for every studied section, without being asked. A key point is one result, rule, definition or method the learner should be able to state and use without the lesson in front of them. Each one has:

- a **statement**, with its formula when it has one;
- **when it holds**: the conditions under which it holds or applies;
- a **common mistake**: preferably one this learner made (a course-memory difficulty or a missed check question).

Each point also links back to the lesson turn that taught it (`turn_id`) and to the pages of its section that present it (`source_refs`). The teacher leaves out "when it holds" or "common mistake" only where a point has none worth stating. It decides how many points a section needs; the host enforces only a sanity cap (12).

### Who writes them, and when

- **The lesson's last step.** Every step's prompt says how to end the lesson. A step that returns an empty `remaining` plan also returns `key_points` in its `<lesson-step>` block, each naming the `step` of the lesson that taught it. The teacher already has the whole lesson and its sources in context (and in the prompt cache), so the points cost no extra turn and are there as the lesson ends.
- **A New lesson** (ADR 0023) is stepped, so its last step rewrites the section's points the same way, from the lesson that now stands.
- **Another pass**, a single reply added to the lesson, may end with a `<key-points>` block. It writes one only when the reply teaches something the points miss or get wrong; otherwise the points stay as they are.
- **The idle job.** For a section studied before key points existed, the idle job writes them on the `key_points` channel from the section's current lesson (not one a New lesson replaced), with the teacher model. A missed last step, or one whose points were refused, is covered the same way. It runs only when nothing else runs, beside preparation and before the prepared review set. It pauses for any request of the learner's and resumes when the host is idle again. The current section is left out while its lesson still has steps to teach. A job that fails is not tried again for the same lessons, so a failing teacher is never retried in a loop.
- **The chapter sheet's paragraph.** Once two or more sections of a chapter have points, the idle job writes one short paragraph on how they connect, on the `chapter_sheet` channel with the small model. It records which points it was written from (`basis`). When any of those points change, the paragraph is stale and is written again when idle. The points themselves are always read live.

### The learner asks Codex to change them

The learner cannot edit key points. The points are the teacher's summary, and an edited summary would drift from what the lessons say. Wording, emphasis and mistakes are what the learner wants to change, and those go through Codex: "say it without the matrix notation", "add the sign convention", "this one is wrong".

- **The Codex operation.** `key_points.revise` replaces a section's points and records the learner's request in their words. It is part of the skill's stable contract, together with `key_points.view` (docs/stability.md).
- **When a lesson rewrites the points.** The teacher is given the current points and the learner's earlier requests. It keeps those changes unless what was taught contradicts one, and it marks a point it keeps unchanged with `kept`, so the point keeps its links.
- **Where the learner asks.** Every key points box links to Studio with the request started.

### Where they show

- **At the end of the lesson**, at the learner's position, once no step is left to teach and none is being written.
- **At the top of a finished section** the learner comes back to.
- **On the chapter page**, as the **chapter sheet**: the paragraph, then each studied section's points in route order. A section whose points are still being written is counted, not hidden.

A point's **Step N** (or **Lesson**) link opens its section at the lesson turn that taught it. Its citations peek and open like the lesson's own.

### The chapter recap goes

Nothing starts a recap any more: the endpoint and its prompt are gone, and an old recap cannot be regenerated (`recap_retired`). Recaps written before stay on their chapter page, folded under **Earlier chapter recaps**, with their highlights and notes. They are still chapter-owned turns (ADR 0006), so nothing that lists a section's lessons counts them. The chapter quiz is unchanged for now. It moves into the Review place with the rest of the review rework.

### Storage

Key points are stored as `key_points/<concept_id>`: `points`, `origin` (`lesson`, `backfill` or `codex`), the `turn_id` that wrote them, `written_at` and the learner's `requests`. Chapter sheets are stored as `chapter_sheets/<chapter_id>`: `connection`, `basis`, `turn_id` and `written_at`. Both are new namespaces, so no existing record changes shape and no migration is needed. A course package at Route and lessons carries both (ADR 0020), without the sender's requests. A point keeps its `turn_id` only when that lesson travels with it.

## Not chosen

- **Points written on request.** That is the recap's failure again: what has to be asked for is not there when it is needed.
- **Learner-editable points.** An edit would go stale the next time the section is taught, and learners already have highlights and notes for their own words (ADR 0005).
- **A separate turn after every lesson.** It would cost a turn per section and leave a gap at the end of each lesson. The idle job does this only for sections the last step did not cover.
- **Writing the chapter paragraph in the last step of a chapter's last section.** Learners study out of order, so "last" is often not last. A paragraph tied to the points it read, rewritten when they change, stays right.
- **Key points per section as review targets with their own schedule.** ADR 0014 already rejected scheduling per key idea, and review is being reworked around a Review place, not a schedule.
