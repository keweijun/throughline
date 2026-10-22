# Curriculum operations

Use the same JSON entrypoint as [course operations](course-operations.md). The teacher extracts concepts and judges learning dependencies; the program validates references and stores the proposed route.

## Build or revise

`curriculum.save` accepts a complete model:

```json
{
  "op": "curriculum.save",
  "concepts": [{
    "id": "wavefunction",
    "title": "Interpret a wavefunction",
    "prerequisites": [],
    "links": [{"source_id":"src-...","revision":"sha256...","unit_id":"page-3","detail":"Probability interpretation"}],
    "notations": [{"symbol":"psi","meaning":"Position representation of the state","source_id":"src-...","revision":"sha256...","unit_id":"page-3"}],
    "exercises": [{"question":"7(a)","source_id":"src-...","revision":"sha256...","unit_id":"page-3"}]
  }],
  "route": ["wavefunction"],
  "coverage": [{"source_id":"src-...","revision":"sha256...","unit_id":"page-3","disposition":"mapped","concept_ids":["wavefunction"],"verification":"pending"}]
}
```

Use stable concept IDs across edits. Merge duplicate concepts with multiple links, preserving incremental details, notation and exercise subquestions. Each link references an exact registered revision and extracted unit. The route contains every concept once with prerequisites first; unknown references and cycles are rejected atomically. Existing concept IDs remain present so earlier evidence can still refer to them.

Coverage dispositions:

- `mapped`: nonempty concept IDs, each with a matching link to that current source unit.
- `deferred`: explicit reason, preserving the content for later teaching.
- `needs_review`: explicit reason for uncertain extraction, mapping or interpretation.

Default `verification` is `pending`. Set `verified` only after checking the contents and include a `verification_note` describing that review. Mapping a page to a concept is a navigation link, not proof every formula, image or detail on it was extracted or taught.

Changes to the relative order of existing concepts require the learner's agreement; then pass `confirm_reorder: true`. Adding a node without changing existing relative order is a local revision. Keep stable IDs and defer content instead of deleting concepts.

## Inspect and teach

- `curriculum.view`: complete stored concepts, route and mapping model.
- `curriculum.coverage`: live units, current source statuses and `stale_mappings`. New units are unmapped; units whose revision changed require review. Stored prior mappings remain available. Failed extraction overrides optimistic mapping status. `semantic_completeness` explicitly requires teacher review.
- `curriculum.context` with `concept_id`: selected concept, direct prerequisite concepts, next concept ID, saved position and only the selected concept's linked source excerpts. Omitting the ID reads `course.position.concept_id`. Source excerpts carry `stale`; verify updated material before relying on an old excerpt.

Before a source update, save the current position. Re-registering material recalculates coverage when queried and leaves learning evidence untouched. Update links and re-review mappings to the new revision; an old mapped revision cannot be submitted as current coverage. Check `curriculum.coverage` before describing a course as fully covered.

Storage namespace is `curriculum`, key `model`. Teaching and evidence modules should use the operations or read this model without modifying its schema. Focused context deliberately excludes the full course text and conversation history.
