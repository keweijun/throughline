# V1 task breakdown

Status: task size, dependencies, and testing boundaries confirmed and published as GitHub Issues. Each task delivers a demonstrable path, skill instructions, and necessary validation rather than horizontal database/script/skill layers.

## 1. Create a course, register materials, and resume

Dependencies: none.

Deliver a unified skill-guided operation entrypoint for creation, ordinary local PDF/Markdown registration and read results, position saving, and reopening the same course from a new process.

Acceptance: stable source IDs and traceable locations; visible failures/pending verification; course isolation; no lost records on duplicate registration or reopen; one small fixture spans creation, reading, saving, and resuming. This does not establish full-course extraction.

## 2. Build an auditable cross-document route

Depends on 1.

The teacher organizes concepts, prerequisites, notation comparisons, and exercise mappings; the system validates coverage/routes and provides focused context.

Acceptance: multiple sources can map to one concept while retaining added details; reject unknown references and cycles; map, defer, or mark page content for review; expose the route; recheck affected content after updates while retaining evidence; confirm major reordering.

## 3. Route-aware answers and mainline continuity

Depends on 2.

Handle brief answers, key foundations, future knowledge, and repeated difficulties around the current goal. Retain restore points and pending explanations; revisit linked nodes.

Acceptance: resume after brief branches, wait after long ones, prioritize explicit depth, recover interrupted branches, change strategy for repeated difficulty, record actual interactions, and validate program state separately from teaching replay.

## 4. Section practice, evidence, and deferred review

Depends on 2.

Support grouped practice, hints, full demonstrations, and skipping, distinguishing learning states by actual evidence. Resume with a brief recap and revisit deferred work at agreed points.

Acceptance: self-reports and teacher answers are not independent learner work; link hint count/degree to evidence; allow continuation; prevent duplicate counting; require valid evidence for progress; show timely review rather than reminders every turn. This can precede the independent branch implementation in task 3.

## 5. Recoverable Luna consolidation and fallback

Depends on 3 and 4.

Create optional consolidation tasks from real teaching/practice interactions. Host-provided Luna may produce candidates; otherwise preserve pending tasks while the teacher uses current state.

Acceptance: demonstrate submit, pause, resume, and retry; results carry evidence and versions; stale results preserve newer interactions and retries are idempotent; no automatic paid API calls; report real-host and unavailable-host cases honestly. Dependencies ensure conflict checks cover actual teaching and evidence states rather than an empty queue.

## 6. Import eight documents and complete teaching acceptance

Depends on 1–5.

Build a local coverage map from the actual eight documents and validate wavefunctions → eigenstates → projection. Finish installation/usage documentation and acceptance reporting.

Acceptance: explicit read/coverage status per source; spot-check formulas, images, and page mappings; do not complete unverified content; replay notation, key foundations, future knowledge, repeated difficulty, skipping, and reopen; simulate missing Luna; run all tests and standards/spec review. List teaching, real-model, and material-validation failures separately; synthetic fixtures do not replace real-material acceptance.

## Dependencies

1 → 2 → {3, 4} → 5 → 6.

The user confirmed this scope, graph, and testing boundary. The six tasks correspond to GitHub #2–#7 and were implemented in dependency order. Program, materials, teaching replay, and model integration results are separate in acceptance-v1.md.
