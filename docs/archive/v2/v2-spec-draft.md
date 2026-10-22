# V2: an independent interface preserving learning continuity

Status: design, task breakdown, and validation boundaries confirmed; implementation and final acceptance complete on 2026-10-19. See acceptance-v2.md.

## Problem Statement

Full lessons commonly take two or three minutes. Learners have difficulty locating themselves and understanding each topic's role in the route. Side questions need prompt answers without burying the mainline. The earlier recording process generated the full lesson twice, adding delay.

## Solution

Prioritize a personal independent learning interface using the existing course workspace. Generate a lesson once, stream it, and let the program save it. Course navigation and unit overviews maintain orientation; branches, sources, and practice support the mainline. Prepare by section in the background and use measured benefits to decide further expansion.

## User Stories

As a learner, I want to:

1. See course contents and my current goal to know where I am.
2. Automatically see the core problem, steps, connections, and target ability at a major unit's start.
3. Preview concepts without changing teaching position.
4. Read full lessons as they stream, reducing empty waiting.
5. Keep my reading position when new paragraphs appear.
6. Ask about a sentence or formula without restating context.
7. Run ordinary side questions alongside the mainline.
8. Receive route-aware answer depth balancing current understanding and later topics.
9. Decide whether to accept foundation supplements.
10. Stop further generation promptly when I explicitly pause.
11. Return to the mainline restore point after a supplement.
12. Open the corresponding original page from a citation.
13. Practice at section ends and freely request hints, steps, or solutions.
14. Defer practice while keeping it pending and controlling advancement.
15. Record viewing answers, hearing explanations, and independent work separately.
16. See preparation readiness separately from learning state.
17. Continue with main-teacher preparation when background work fails.
18. Restore goals, position, and unresolved questions across sessions.
19. Save lessons automatically without duplicate retry records or note-taking delay.
20. Use auxiliary views in narrow windows.

## Implementation Decisions

- The workspace remains the sole official learning state. Reuse course operations, sources, routes, evidence, and teaching recovery; the UI has no second progress store.
- Prioritize an independent UI with left navigation, central teaching, and an optional right auxiliary area. Start with the right area closed; preserve position when switching branches/sources and use a drawer on narrow screens. Visual styling was undecided at specification time.
- Generate one formal reply. The host receives streamed content and associates authoritative completion text with course records, without prewriting and repeating a script.
- Expose pause, disconnect, and unfinished states. Partial text is not completed teaching; repeated events do not duplicate evidence. Validate transport capability before choosing continuation versus regeneration.
- Ordinary branches do not advance the mainline. Suggest prerequisite supplements and pause/adjust only on acceptance. Execute explicit pause directly; stop and correct confirmed lesson errors.
- Begin the first section directly after its overview. The learner advances sections without a compulsory practice pass. Taught content, pending exercises, and mastery evidence stay separate.
- Plan the unit, prepare by section, and default to one section ahead with at most one active preparation task. Foreground teaching/questions take priority; the main teacher performs necessary checks if preparation is unavailable.
- Associate preparation with source/route versions. Irrelevant or stale results cannot overwrite newer routes or learning state. Background lifecycle after departure was unverified; no always-on guarantee.
- Prefer the tested model channel. Concurrency, cancellation, contention, and course transaction association require integration checks rather than prototype evidence.

## Testing Decisions

Use the public course-operation boundary for official state, add client-to-model event-stream integration, and verify visible interaction through a few browser scenarios.

- Course behavior: preview isolation, branch recovery, no mastery upgrades from skipping/solutions, new-process recovery, and stale/retry protection. Reuse course, teaching, evidence, and background tests.
- Streaming: pass real events through the adapter; compare displayed and authoritative text and save once. Simulate duplicate/out-of-order events, disconnect, and pause without presenting simulations as service capability.
- Browser: selected-passage questions, branch return, original pages, supplement pause/recovery, defer/advance, and no forced scroll jumps.
- Real integration: at least one full output/save, one pause/recovery, and one concurrent mainline/branch run. Model doubles cannot establish real concurrency.
- Performance: time the first 200 substantive characters, full reply, save, and immediate questions with/without preparation. Preserve goal, length, and quality; report distributions and failures, without turning earlier three-pair results into an SLA.
- Teaching replay: review answer depth, continuity, hints, and key concept coverage separately from program tests.

## Out of Scope

Obsidian integration, multi-user accounts, a full Codex desktop mirror, public plugins, a mobile-specific app, chapter-wide pregeneration, and automatic additional paid providers. The prototype is not final visual design or production code.

## Further Notes

Three single-output pairs reduced aggregate full-reply time by about 37%, with average first-200-character time falling from about 90 to 31 seconds in an isolated client. The sample is small. Preparation benefits were inconsistent, so implement single output before measuring concurrency and preparation.

The user accepted the interaction direction; no per-scenario user logs establish completion of every walkthrough. Prototype preservation and issue links belong to publication. This extends V1's UI scope without changing state ownership.

Prototype reference: learning-flow.prototype.html. At specification time, real-model/browser integration acceptance was still pending.
