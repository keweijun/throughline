# Chapters group the route; sections teach one core question

Lecture notes often have dozens of small sections. Teaching each as its own section scatters the course, but merging them into a few large sections makes every lesson a long lecture: concepts blur together on first contact, and when practice goes wrong it is hard to tell which step the learner missed. A single `curriculum.save` call carrying the whole route also forces Codex to write one very large JSON for a big course, where one mistake rejects everything.

We separate the two levels:

- A **chapter** is a table-of-contents grouping. It is never taught as one block.
- A **learning section** answers one core question, with closely related ideas explained together and missing prerequisites bridged first. It is still the unit for lessons, practice, evidence and coverage, so none of those change.

Nothing fixes how many chapters a course has, how many sections a chapter has, or how long a lesson is. The teacher decides from the materials, the learner profile and the content of each section. The fixed word range previously given to every lesson is removed.

## Storage and operations

The curriculum model gains optional `chapters: [{id, title, summary?, concept_ids}]`. When present, chapters list every route concept exactly once and in route order, so the route is the chapters' sections joined. A chapter with no sections is not built yet. A course always has at least one chapter once it has a route: `curriculum.save` without chapters, on a course that has none or only the whole-course chapter, groups the whole route into one chapter (id `course`) titled after the course, and courses saved before chapters existed are migrated the same way (ADR 0007). The flat-route teaching path, a unit overview on every section's first lesson, is retired; "About this section" still shows each section's core question and objective.

Codex builds a course chapter by chapter: `curriculum.outline` saves the ordered chapters, then `curriculum.chapter.save` saves one chapter's concepts and upserts the coverage entries for its pages. `curriculum.chapter.view` reads one chapter back. Every write is validated against the whole merged model in one transaction (prerequisites, cycles, stable IDs, coverage, reorder confirmation), which is why chapters live in the one curriculum model instead of separate stores. A source unit used by two chapters keeps both chapters' concepts and is mapped if either chapter maps it. The course can be studied as soon as its first chapter is built.

## Teaching

- The first lesson of a chapter's first section opens with a chapter overview. Later sections open with a short bridge from the previous section instead of a unit overview.
- At the end of a chapter the learner may ask for a recap: a mainline lesson in the chapter's last section that connects its sections and lists set-aside exercises. It teaches nothing new and adds no exercises.
- The learner may skip the rest of a chapter. Its remaining sections are deferred with `evidence.defer` (`section_id` is the chapter) and stay on the route, marked as skipped; the learner can go back and study one, and its next lesson resolves the deferral. No mastery gate is added.
- Practice is unchanged: grouped at the end of each section.

## Consequences

- Moving concepts between chapters or reordering chapters needs the learner's agreement when it changes the relative order of existing concepts or chapters (`confirm_reorder`).
- Building a later chapter happens in the app in the background, or in Codex (ADR 0004).
