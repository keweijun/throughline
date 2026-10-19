# Section practice and learning evidence

A section covers a complete learning goal and ends with grouped practice. Read `evidence.review` first and choose exercises for the current goal. When the learner is stuck, give the minimum necessary hint, then wait for an attempt. Demonstrate a full solution when explicitly requested. On continuation or skipping, preserve unverified status and advance. The teacher judges correctness; the program checks evidence roles, references, ordering, and deduplication. Program acceptance does not establish a correct answer.

## Recording flow

1. Save actual text with `interaction.record` and obtain IDs for the learner answer and teacher explanation. Use a new `session_id` per learning session; retain the same `exercise_id` for retries and hints on one question. Select from course exercise mappings and keep a stable exercise identifier.
2. `evidence.record` accepts `id, concept_id, kind, interaction_id`. `kind` is `taught` (teacher explanation), `self_report` (learner statement), `hint`, or `demonstrated` (full demonstration). Hints and demonstrations also require `session_id, exercise_id`; hints need `level`, such as `minimal` or `worked_step`. Record all assistance before assessment. Backfilling prior hints after historical assessment is rejected; report the recording gap explicitly.
3. Assess only after an actual learner answer. Record teacher feedback with reasons, then submit `evidence.assess`: `id, concept_id, session_id, exercise_id, answer_id, assessment_id, outcome`. Use `passed` or `needs_work`. Feedback must follow the answer. Passing after hints/demonstrations becomes `hinted`; passing without help becomes `independent`. Continuing, saying "I understand," and teacher answers are not learner-answer evidence; use `self_report` for self-reports.
4. For a delayed retest, set `retest_of` to a previous independent pass and use a new answer from another session. Only an unassisted pass produces `retest_passed`. The same original answer cannot be assessed again under a new ID.
5. Check `evidence.view {concept_id}`. `status` is the highest historical evidence level; also read `latest_assessment`, which may show a later failure. `independently_verified` means at least one independent pass, not permanent mastery or a probability. History and interaction references remain available.

Example assessment:

```json
{"op":"evidence.assess","id":"assessment-7a-1","concept_id":"projection","session_id":"session-2","exercise_id":"exercise-7a","answer_id":"user-answer-7a","assessment_id":"teacher-feedback-7a","outcome":"passed"}
```

## Deferral and reopening

- `evidence.defer` accepts `id, concept_id, reason`, plus `target_concept_id` or `section_id` (or both). Skipping registers a deferral and preserves existing evidence.
- Call `evidence.review {concept_id, section_id?, recap?}` on entering a target concept or section recap. Set `recap:true` only for recaps. `due` provides scheduled items; do not reread or remind on every answer.
- On reopening, use `session.resume` and `evidence.review` for a brief goal/question recap, then continue. `quiz_required:false`; no mandatory test. Learners can still choose to advance.
- When the learner confirms a revisit, record the actual response, then call `evidence.resolve {id, deferred_id, interaction_id}`. This ends reminders without upgrading mastery; history remains in `deferred_history` and `resolutions`.

Same-ID/same-content retries return the original record; changing existing content returns `id_conflict`. Create an explicit new correction event and retain original evidence. Evidence survives source updates; the teacher decides whether new materials warrant a retest.

## Historical sources and original-text checks

New evidence preserves source snapshots from original interactions: explanation/self-report records use `source_refs`; assessments separately preserve `answer_source_refs` and `assessment_source_refs`. Each entry contains source ID, content-revision SHA, and unit ID. References still point to that revision after source changes or curriculum relinking. Inspect it with `source.read {source_id, revision}` rather than interpreting old evidence through current links.

Use `interaction.read {id}` for the original answer and feedback even beyond the most recent 20 messages. Missing or empty source fields in older records mean no usable source was recorded; do not backfill the latest revision. Historical retries retain their original values.

When item A is due at concept B, `evidence.resolve` accepts an actual learner confirmation tagged with A or the agreed target B and retains its interaction ID. Do not retag the original message. Existing untagged learner messages remain compatible; unrelated concepts and teacher messages are rejected.
