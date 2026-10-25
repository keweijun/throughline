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

## Chapters

Group the route into chapters, the course's table of contents. A chapter is never taught as one block; each concept in it is one learning section that answers one core question. Explain closely related ideas in the same section, and give a prerequisite its own earlier section when several sections rely on it. Take the number of chapters and sections from the materials and the learner's goal; there is no target count. Follow the materials' own chapters where they fit the learning order.

Build a course chapter by chapter so no single call carries the whole route:

1. `curriculum.outline` with `chapters: [{id, title, summary?}]` in teaching order. `summary` is one or two sentences on the chapter's core problem. Existing chapters keep their concepts; give `concept_ids` (existing concept IDs) to assign or move them, which is how a flat route is first grouped. Omitting a chapter that still has concepts is rejected.
2. `curriculum.chapter.save` with `chapter_id`, `concepts` in teaching order (the same concept objects as `curriculum.save`), optional `title`/`summary`, and `coverage` entries for that chapter's source units. Concepts not listed elsewhere are replaced; listing a concept from another chapter moves it here. Coverage entries are upserted by source unit; entries you do not send stay. A unit that another chapter maps keeps that chapter's concepts too and stays `mapped`.
3. Read a chapter back with `curriculum.chapter.view {chapter_id}` (its concepts and coverage) instead of the whole model when revising it.

Prerequisites must be in the same or an earlier chapter that is already built. Build chapters in order, read only that chapter's sources for each, and open the course after the first chapter so the learner can start; build the rest in the same run unless the learner asked for one chapter at a time. A request like `$throughline build the chapter "<title>" of the course <name>` means: build that outlined chapter. A chapter with no concepts shows as not built yet.

`curriculum.save` still accepts a complete model and an optional `chapters` array (each with `concept_ids`); without it the stored chapters are kept, so a new concept must then be placed through `chapters`, `curriculum.outline` or `curriculum.chapter.save`. With chapters, their `concept_ids` joined in order must equal the route. Reordering existing chapters, or moving concepts so their relative order changes, needs `confirm_reorder: true` after the learner agrees.

## Inspect and teach

- `curriculum.view`: complete stored concepts, route and mapping model.
- `curriculum.coverage`: live units, current source statuses and `stale_mappings`. New units are unmapped; units whose revision changed require review. Stored prior mappings remain available. Failed extraction overrides optimistic mapping status. `semantic_completeness` explicitly requires teacher review.
- `curriculum.context` with `concept_id`: selected concept, its `chapter` (with `index` and `total`, or null), direct prerequisite concepts, next concept ID, saved position and only the selected concept's linked source excerpts. Omitting the ID reads `course.position.concept_id`. Source excerpts carry `stale`; verify updated material before relying on an old excerpt.

Before a source update, save the current position. Re-registering material recalculates coverage when queried and leaves learning evidence untouched. Update links and re-review mappings to the new revision; an old mapped revision cannot be submitted as current coverage. Check `curriculum.coverage` before describing a course as fully covered.

Storage namespace is `curriculum`, key `model`. Teaching and evidence modules should use the operations or read this model without modifying its schema. Focused context deliberately excludes the full course text and conversation history.
