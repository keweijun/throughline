# Teaching with a persistent mainline

At session start call `session.resume`. Briefly recover the saved goal and next step, any active sidequestion, and due explanations. A waiting branch means the learner is still considering a long answer; resuming the chat does not advance it. Recent messages are bounded (default 8, maximum 20), while raw records stay durable.

For each actual learner message, call `interaction.record` before teaching. Use the current curriculum context to choose response depth yourself. Persist the actual assistant response and the checkpoint before returning it to the learner. Record original wording, not a summary or an imagined learner answer. IDs are unique per message; retries reuse the same ID and payload. Background note generation may follow a small section; the foreground response does not wait on Luna.

## Decide depth from the route

- Local symbol/definition: enough detail to use the current equation; short answer can rejoin the mainline immediately.
- Missing prerequisite: explain the necessary bridge now. Use a long answer when the current lesson depends on it; leave room for follow-up.
- Future concept: give a useful provisional intuition and its limitation now; bind the deferred full explanation to a route concept. If the learner explicitly asks to go deeper, explain now.
- Repeated confusion: identify whether notation, mathematics, intuition or model choice is missing. Use `new_example`, `concept_bridge`, or `alternative_representation` rather than repeat the explanation.
- Extension: answer proportionally to the current goal and the learner's interest.

These are teacher judgments, not text-matching rules. Record the rationale. A category label does not itself guarantee a good explanation; the teaching replay must assess that separately. Keep section-end practice rather than adding a quiz after every small question.

## Operation requests

Use the course JSON CLI. Each mutation is atomic.

- `interaction.record`: `{id, role:"user"|"assistant", text, concept_id?}` returns `{interaction}`. Concept is optional; role is the actual speaker. Identical retries succeed, conflicting ID reuse fails. Records contain a monotonic `sequence`.
- `mainline.enter`: `{concept_id, goal, next_step, progress?}` saves the current position and returns `due_explanations`. No mastery gate prevents the learner choosing the next concept. Close an active branch through `sidequestion.continue` when the learner chooses to continue.
- `sidequestion.open`: `{id, interaction_id, category, depth:"short"|"long", rationale, strategy, explicit_deepen?, target_concept_id?}` saves the exact mainline restore point. Categories are `local`, `prerequisite`, `future`, `repeated`, `extension`. `interaction_id` must identify the actual user question. Future questions require a valid target. `explicit_deepen:true` forces long depth even if short was proposed.
- `sidequestion.answer`: `{id, answer_interaction_id}` links a subsequently recorded assistant message. Short answers restore the mainline; long answers become `waiting`. A short future answer creates a pending full explanation. Long future answers are the immediate full explanation, so the teacher must actually provide it.
- `sidequestion.continue`: `{id}` after the learner chooses to resume. Unanswered questions stay visible as unanswered; continuing never pretends they were solved. Record the learner's continue message with `interaction.record` as usual.
- `deferred.create`: `{id, interaction_id, provisional_answer_interaction_id, target_concept_id}` binds a future explanation after a real user question and later assistant provisional answer. It preserves any active branch and its restore point. Retries preserve pending/resolved status; conflicting IDs fail. The target must be a curriculum concept.
- `deferred.resolve`: `{id, answer_interaction_id}` after actually providing the full explanation. Merely reaching the target leaves the item pending. The answer must occur after the provisional answer.
- `session.resume`: `{recent_limit?}` returns position, focused curriculum context, active branch, due explanations, unanswered questions and recent actual interactions.

A single active branch keeps a stable mainline. Follow-up questions inside a long explanation remain recorded interactions in that branch; avoid overwriting its restore point. If such a follow-up needs a later full explanation, first record its actual question and useful provisional answer, then call `deferred.create` with a unique promise ID and target concept. Leave the existing branch waiting until the learner chooses to continue. At the target, `due_explanations` surfaces this promise through the existing resume/enter operations; provide the full explanation and call `deferred.resolve`. A new unrelated branch begins after continuing the old one. For substantive new learning position changes use `mainline.enter`; `position.save` remains the low-level checkpoint operation.

## Integration contract

Namespaces: `interactions` keyed by message ID; `sidequestions` by branch ID; `teaching/active_branch` stores its ID; `deferred_explanations` by unique promise ID (the originating branch ID for auto-created future branches). Interaction records are immutable `{id,role,text,concept_id,sequence}`. Evidence operations may link them and check roles but should not mutate raw messages. Summary or background output never replaces these messages.
