# Curriculum operations

Use the same JSON entrypoint as [course operations](course-operations.md). The teacher extracts concepts and judges learning dependencies; the program validates references and stores the proposed route.

## Chapters and sections

Group the route into chapters, the course's table of contents. A chapter is never taught as one block; each concept in it is one learning section that answers one core question. Explain closely related ideas in the same section, and give a prerequisite its own earlier section when several sections rely on it. Take the number of chapters and sections from the materials and the learner's goal; there is no target count. Follow the materials' own chapters where they fit the learning order.

## Build a course chapter by chapter

Build chapter by chapter so no single call carries the whole route:

1. `curriculum.outline` with `chapters: [{id, title, summary?}]` in teaching order. `summary` is one or two sentences on the chapter's core problem. Existing chapters keep their concepts; give `concept_ids` (existing concept IDs) to assign or move them, which is how a flat route is first grouped. Omitting a chapter that still has concepts is rejected.
2. `curriculum.chapter.save` with `chapter_id`, `concepts` in teaching order (concept objects, below), optional `title`/`summary`, and `coverage` entries for that chapter's source units. List every concept of the chapter, existing ones included: a concept you leave out drops off the route and the save is rejected. Listing a concept from another chapter moves it here. Coverage entries are upserted by source unit; entries you do not send stay. A unit that another chapter maps keeps that chapter's concepts too and stays `mapped`.
3. Read a chapter back with `curriculum.chapter.view {chapter_id}` (its concepts and coverage) instead of the whole model when revising it.

Prerequisites must be in the same or an earlier chapter that is already built. Build chapters in order and read only that chapter's sources for each. Open the course after the first chapter so the learner can start. The app can build an outlined chapter itself, in the background, from the registered sources: when the learner starts the last built chapter, or chooses "Build this chapter". So outline every chapter first; then build the rest in the same run, or stop after the first chapter if the learner prefers to let the app build them. A chapter with no concepts shows as not built yet.

A request like `$throughline build the chapter "<title>" of the course <name>` comes from the app's fallback link and means the app's own build of that chapter failed: build that outlined chapter here, checking its sources and `curriculum.coverage` for what made the build hard (unreadable pages, material that belongs to another chapter).

## Concept objects

```json
{
  "id": "wavefunction",
  "title": "Interpret a wavefunction",
  "core_question": "What does the wavefunction tell us about where a particle will be found?",
  "objective": "Compute position probabilities from a normalized wavefunction",
  "overview": {
    "core_problem": "Quantum states are complex functions, yet measurements give real probabilities.",
    "steps": ["Born rule", "Normalization", "Probability in an interval"],
    "target_ability": "Normalize a wavefunction and compute the probability of finding the particle in a region"
  },
  "prerequisites": [],
  "links": [{"source_id":"src-...","revision":"sha256...","unit_id":"page-3","detail":"Probability interpretation"}],
  "notations": [{"symbol":"psi","meaning":"Position representation of the state","source_id":"src-...","revision":"sha256...","unit_id":"page-3"}],
  "exercises": [{"question":"7(a)","source_id":"src-...","revision":"sha256...","unit_id":"page-3",
                 "required_concepts":["wavefunction"],"part_of":"7","other_parts":[{"question":"7(b)","concept_id":"expectation-values"}]}]
}
```

Give every section a `core_question` (the one question the section answers, phrased as the learner would ask it) and an `objective` (what the learner can do afterwards, specific to this section). The app shows them as the section's goal and in "About this section", and the teacher builds the lesson around them; without them the app falls back to generic text. `overview` is optional: `core_problem`, `steps` (about three, each naming specific ideas), `prior`, `next` and `target_ability`, all strings except `steps`. Write these in the course's teaching language.

Use stable concept IDs across edits. Merge duplicate concepts with multiple links, preserving incremental details, notation and exercise subquestions. Each link references an exact registered revision and extracted unit. The route contains every concept once with prerequisites first; unknown references and cycles are rejected atomically. Existing concept IDs remain present so earlier evidence can still refer to them.

## Exercise placement

An exercise part goes in the latest section among the concepts it requires, never earlier, so a lesson never has to teach ahead of the route. Give every exercise `required_concepts`: the IDs of all sections the part needs, its own section included. A save is rejected (`exercise_placement`, naming the exercise and the concept) when a required concept comes later in the route or is not in it; reordering chapters or moving a concept that would leave an exercise too early is rejected the same way. Deadlines do not change this: a learner who needs a part sooner can study the sections it needs, or ask a side question.

Split homework by part. When the parts of a question need different sections, map each part (`7(a)`, `7(b)`) as its own exercise on the latest section it requires, with `part_of` naming the original question (`7`) and `other_parts` listing the other parts with the `concept_id` of the section that teaches each. When building chapter by chapter, a part that needs a chapter not built yet waits: list it in `other_parts` without `concept_id`, map it when you build that chapter, and then add its `concept_id` to the earlier part. The app's own chapter builds receive such waiting parts with their source text.

`curriculum.check` reads the stored course and changes nothing. It returns `violations` (one per misplaced exercise: `concept_id`, `chapter_id`, `question`, its source reference, `later_concepts`, `unknown_concepts` and `move_to`, the latest required section already on the route), `exercises` (how many are mapped) and `without_required_concepts` (how many do not say what they need yet, which the check cannot judge). Courses saved before this rule may hold violations; they still open and teach. Run the check before revising such a course, and fix the violations chapter by chapter: a save rejects violations in the concepts it sends and any it creates, but keeps earlier violations in concepts it does not send, so `curriculum.chapter.save` of one chapter succeeds while another chapter is still misplaced. `curriculum.save` sends every concept, so it needs the whole course fixed.

## Coverage

Coverage dispositions:

- `mapped`: nonempty concept IDs, each with a matching link to that current source unit.
- `deferred`: explicit reason, preserving the content for later teaching.
- `needs_review`: explicit reason for uncertain extraction, mapping or interpretation.

Default `verification` is `pending`. Set `verified` only after checking the contents and include a `verification_note` describing that review. Mapping a page to a concept is a navigation link, not proof every formula, image or detail on it was extracted or taught.

## Revising and reordering

Changes to the relative order of existing concepts or chapters require the learner's agreement; then pass `confirm_reorder: true`. Adding a node without changing existing relative order is a local revision. Keep stable IDs and defer content instead of deleting concepts.

`curriculum.save` accepts a complete model (`concepts`, `route`, `coverage`, optional `chapters` each with `concept_ids`) in one call. Prefer the chapter operations; use it for small courses or whole-model repairs. Without `chapters`, a course with no chapters of its own becomes one chapter titled after the course (id `course`), which follows the route until you outline real chapters; otherwise the stored chapters are kept, so a new concept must then be placed through `chapters`, `curriculum.outline` or `curriculum.chapter.save`. With chapters, their `concept_ids` joined in order must equal the route.

## Inspect

- `curriculum.view`: complete stored concepts, route, chapters and mapping model.
- `curriculum.coverage`: live units, current source statuses and `stale_mappings`. New units are unmapped; units whose revision changed require review. Stored prior mappings remain available. Failed extraction overrides optimistic mapping status. `semantic_completeness` explicitly requires teacher review.
- `curriculum.check`: exercise placement violations in the stored course (above); read-only.
- `curriculum.context` with `concept_id`: selected concept, its `chapter` (with `index` and `total`, or null), direct prerequisite concepts, next concept ID, saved position and only the selected concept's linked source excerpts. Omitting the ID reads `course.position.concept_id`. Source excerpts carry `stale`; verify updated material before relying on an old excerpt.

Before a source update, read the course status. Re-registering material recalculates coverage when queried and leaves learning evidence untouched. Update links and re-review mappings to the new revision; an old mapped revision cannot be submitted as current coverage. Check `curriculum.coverage` before describing a course as fully covered.

Storage namespace is `curriculum`, key `model`. Other modules should use the operations or read this model without modifying its schema. Focused context deliberately excludes the full course text and conversation history.
