# Learning workflow improvement recommendations

Research date: 2026-10-12 (user timezone). Based on a full reading of the specified Obsidian conversation and associated route/progress files. Product claims were checked against official documentation/repositories without installation. The user additionally reported that DeepTutor Mastery Path did not meet cross-document guidance needs and had document-reading bugs. This is a historical research proposal; later confirmed V1 decisions supersede its Obsidian and default-check suggestions.

## Judgment

Separate course maps, learning evidence, and teaching conversations. Let background models maintain notes/materials while a foreground teacher responds around a clear goal. At this research stage, the suggestion was to keep Obsidian as a source/note destination and potentially move learning into a dedicated interface.

RemNote merits a small trial; DeepTutor is conditional; OpenMAIC fits interactive classrooms. Reviewed documentation does not establish that any candidate fully meets reliable cross-lecture long-term guidance, so independent course state/scheduling may still be needed.

## Diagnosis of existing records

1. **Planning exists; execution constraints are weak.** The route has 11 stages, prerequisites, and L0–L4 standards. Progress reaches stage 6 but independently completed stages/full exercises remain 0/11. The records honestly avoid mastery claims, but accumulating pending checks do not sufficiently affect subsequent teaching.
2. **Prerequisite gaps appear after derivation.** Twice the learner asks why a state is a function and what its variable is, then asks how the expectation formula relates to averaged measurements. Add brief conceptual checks before eigenstates, projection, and Hermiticity, and carry unresolved questions forward.
3. **Pace is uneven.** Simple momentum/wavelength calculations were split across many turns, while repeated continuation later produced complete proofs/solutions. Prefer a whole concept or reasoning step, with options for explanation, hinted practice, and independent checks.
4. **Background bookkeeping enters visible teaching.** Reading progress, source updates, and saving records appear in multiple turns; some openings repeat the body, with one empty reply. Exported text cannot determine whether duplication came from the model or message assembly, or how much latency file operations caused.
5. **Coverage is not auditable.** The route maps files/stages and promises a second pass, without a complete page/section ledger. This does not prove a specific omission, but makes omissions difficult to verify.
6. **Progress feedback is too coarse.** 0/11 is consistent with strict independent completion but cannot express taught content. Show explanation coverage, attempts, independent passes, and review separately rather than one percentage.

Adjacent chat timestamps include reading/absence and cannot measure response latency. Metadata usedTokens is not directly per-turn input length.

## Proposed workflow

### Build a course map during import

Parse/cache all eight materials, retain original files and page/slide locations for formulas/images, and expose success/failure per file/page without silent skipping.

Link:

- Concepts ↔ all source pages where they occur, merging repeated explanations while retaining sources.
- Concepts → prerequisites, such as amplitudes, conjugation, and inner products supporting projection/measurement.
- Each exercise subquestion ↔ required concepts, methods, and grading criteria.

Every source section needs a disposition: mapped, intentionally deferred, excluded with reason, or parsing repair pending. Content coverage and mastery are distinct. Semantic retrieval finds related material without proving completeness.

Relational tables or JSON suffice initially; no complex graph database is required. Version map changes and bind evidence to stable concept IDs.

### Foreground teacher and background work

| Work | Timing | Model/state principle |
|---|---|---|
| Explanation, questions, current-answer feedback | Foreground streaming | Reliable teacher; increase reasoning only for hard derivations |
| Original exchanges and submission events | Fast synchronous write | Programmatic, without an LLM |
| Preference, misconception, and summary extraction | After replies in background | Fast model proposes structured changes with evidence |
| Obsidian notes/review cards, as proposed at this stage | Section end or idle | Batch turns rather than rewrite large files per sentence |
| Coverage gaps/next-section retrieval | Background or source updates | Independent from current teaching |
| Evidence upgrades and next-step selection | When current evidence is available | Rule checks; do not rely entirely on unreviewed summaries |

Each teacher turn needs the goal, necessary source excerpts, relevant prerequisites, unresolved questions, recent dialogue, and current input. Retrieve more history when topics change.

Background updates carry event IDs, evidence message IDs, and state versions. Repeated tasks cannot double-count; stale summaries cannot overwrite new answers. While work is pending, teachers read fresh raw events. Keep unfinished assessments pending rather than automatically passing. Limit background concurrency to preserve foreground capacity.

[LangGraph memory documentation](https://docs.langchain.com/oss/python/concepts/memory) distinguishes checkpoints, cross-session storage, and foreground/background memory tradeoffs. The application still owns curriculum graphs, evidence judgment, and queue rules.

### Make teaching scheduling explicit

Proposed default: one goal → intuition/example → necessary formulas → short check → continue, remediate prerequisites, or practice.

"Continue" advances the current teaching mode rather than establishing mastery. Skipping an integral leaves that skill untested for later checking. Learners may choose explanation-only mode; distinguish heard from passed.

For each concept, independently record teaching status, conceptual and calculation evidence, hint level, specific misconceptions, and the next check. Repeated uncertainty about states/functions should trigger remediation; fluency in scientific notation does not justify accelerating abstract concepts.

[OATutor](https://github.com/CAHLR/OATutor) separates knowledge skills from mastery estimates through Bayesian Knowledge Tracing. Its ready-made content emphasizes math, requiring quantum-course authoring. Transparent evidence levels may be preferable initially to precise-looking probabilities from little data.

### Interface

The research-stage desktop suggestion placed map/review at left, original slides/images/formulas centrally, and tutor/answers at right, with tabs on small screens.

Highlight the goal and one pending question. Offer intuition, hints, derivations, independent practice, and deferral. Collapse solutions; put answers/assessment in distinct cards. Formula selection supports local questions without changing the route. Show sync as status, expanding only on failure.

The original suggestion retained Obsidian sources, exported notes, and readable progress. If building a new system, structured state/database should be authoritative and Markdown an export, preventing dual progress writers. Later project decisions removed Obsidian integration entirely.

## Candidate choices

| Approach | Why it may fit | Remaining work |
|---|---|---|
| RemNote Guided Learn | Learning from documents/folders with closely linked source reading, questions, quizzes, and mastery tracking | Unproven cross-lecture prerequisite fusion; test derivation exercises |
| DeepTutor Mastery Path | Documents describe multi-material paths, missing-file warnings, checks, review, and recovery | User reading failures require regression; selection is not cross-document teaching |
| OpenMAIC | Interactive classroom, whiteboard, simulation, and slides support intuition | Long-term cross-lecture mastery scheduling unconfirmed; generated classes may add delay |
| Open WebUI plus independent course state | Chat shell, documents, task models, background subagents | Missing course-map and evidence rules for this use |
| Chainlit, LangGraph, persistent database | Can prototype question cards, sources, streaming, and recovery | Frameworks still need parsing, planning, scheduling, and interaction code |

RemNote's initial familiarity choice changes activity priority rather than content: [Guided Learn](https://help.remnote.com/en/articles/15724936-guided-learn-mode). It is not automatically a complete adaptive curriculum.

DeepTutor: [Mastery Path](https://docs.deeptutor.info/explore/mastery-path/) and [Task Model settings](https://docs.deeptutor.info/explore/settings/). Documentation does not replace actual acceptance.

OpenMAIC: [official repository](https://github.com/THU-MAIC/OpenMAIC); main may contain prerelease features. Open WebUI [Task Models](https://docs.openwebui.com/features/administration/task-models/) mainly support auxiliary work such as titles/tags, not proof of asynchronous learning memory. [Background subagents](https://docs.openwebui.com/features/chat-conversations/chat-features/subagents/) provide an extension base. Chainlit [custom elements](https://docs.chainlit.io/api-reference/elements/custom) and [streaming](https://docs.chainlit.io/advanced-features/streaming) support a narrow prototype.

See framework-research.md for more product checks, including NotebookLM for source reading and LearnHouse for course organization; neither was the preferred main system here.

## Suggested validation order

1. Retain existing sources/evidence and try a small RemNote sample for daily interaction. Do not migrate everything solely for a convenient UI.
2. Retry DeepTutor only if willing to investigate again. Establish reliable reading of every file before testing route fusion; parser failure makes teaching-quality evaluation premature.
3. If prerequisite scheduling remains inadequate, prototype wavefunctions → eigenstates → projection → exercise 7 with a foreground teacher, background recording, concept state, and source sidebar. Validate that chain before all eight documents.

Acceptance measures:

- All eight sources have parse results or explicit errors; spot-check images, formulas, and locations.
- Cross-query concept/page/subquestion; merge repeated concepts and expose deferred content.
- Repeated questions trigger remediation; continuation/viewed solutions do not raise mastery automatically.
- Reopening preserves tasks, unresolved questions, and answer evidence.
- With the same model/network/materials, separately measure first useful content, full answer, tool waiting, and background completion. Compare multi-turn medians and slow-request percentiles rather than a single impression.
- Background failure does not block teaching; retries are idempotent and stale memory preserves fresh answers.

This round delivered research/design recommendations only; original notes were unchanged and no learning system was installed or switched.
