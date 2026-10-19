# Implementation specification: personal cross-document guided learning V1

Status: testing boundaries confirmed and GitHub specification/tasks published. See acceptance-v1.md for local implementation and layered acceptance.

## Problem Statement

Long-term study across lectures and exercises can drift from the mainline, miss concepts, or confuse hearing an explanation with mastery. Note consolidation and rereading history add waiting. Learners need route-aware answer depth, control over advancement, and accurate continuity across sessions.

## Solution

Combine a reusable Codex skill with an independent course workspace. Retain a source-traceable coverage ledger, prerequisite route, restore points, and answer evidence. The teacher explains and handles branches immediately; Luna optionally consolidates in batches, without blocking teaching on failure. Cover all eight initial documents and validate a representative cross-document learning chain.

## User Stories

As a learner, I want to:

1. Import multiple lecture and exercise documents around one goal.
2. See each source's reading result to discover missing or damaged pages.
3. Locate concepts in original sources to check explanations.
4. Merge duplicate concepts while retaining distinct details.
5. Follow prerequisite-based routes across documents.
6. Review the overall route and disputed choices to adjust direction.
7. Use sections with complete goals and practice at natural closure.
8. Receive brief notation answers followed by a return to the mainline.
9. Fully resolve questions blocking current understanding.
10. Get enough explanation of future concepts for current use.
11. Have earlier questions completed proactively at relevant nodes.
12. Receive different examples or bridges for repeated difficulty.
13. Retain the original goal and resume point after a branch.
14. Get depth immediately when explicitly requested.
15. Practice at section ends without frequent quiz interruptions.
16. Get necessary hints first while retaining a chance to reason independently.
17. View solutions or skip to control pace.
18. Distinguish taught, self-reported, and independent evidence.
19. Restore goals, unresolved questions, and evidence after interruption.
20. Keep existing evidence when materials change.
21. Delegate optional consolidation to Luna so the main teacher can teach.
22. Continue when Luna is unavailable.
23. Have retries and stale results leave newer state intact.
24. Avoid automatic additional paid API calls and retain spending control.
25. Compare notation across lectures to reduce unnecessary confusion.

## Implementation Decisions

- Separate the generic skill from course data; the workspace owns official state, following the accepted ADR.
- Use one course-operation entrypoint for creation, source registration, routes, interactions, recovery, coverage, and consolidation. Internal modules remain adjustable.
- The program owns stable source/concept IDs, prerequisite validation, persistence, and update checks; the teacher owns extraction, explanation, and contextual judgment.
- Save original exchanges and position promptly. Derived summaries cannot replace evidence. Unique operation IDs handle retries; background candidates carry evidence and versions, preserving newer state on conflict.
- Reject invalid prerequisite references and cycles. Check explicit dispositions for content rather than equating successful reading or model extraction with complete teaching coverage.
- Initial materials include PDFs and Markdown transcriptions. Import ordinary local files independently of their original application. Unverified page mappings, formulas, and images remain pending, without invented locations.
- Keep restore points, branches, pending explanations, deferred items, and evidence distinct. Resume after brief answers, wait after long answers, and bind future questions to revisit nodes.
- Route-aware answering is not keyword classification: the program supplies context and validates transitions; the teacher judges the real question and route.
- Group practice at section ends. Retain taught, self-reported, hinted, independent, and retest evidence separately; skipping does not upgrade mastery.
- Luna assistance uses host-provided subagents. Course scripts do not assume direct Codex model access. Record pending work when unavailable rather than simulating successful calls.
- Initial background work is optional within a session and may pause/resume; no persistent service or automatic paid API fallback.
- Small route revisions preserve evidence; major learning-order changes require confirmation.

## Testing Decisions

- At specification time there was no implementation or test framework. Use the public course-operation boundary, check visible results, and reopen from a new process to verify persistence.
- Test visible reading failures, source traceability, cycle rejection, branch recovery, due explanations, skipping without evidence upgrades, evidence/source links, stale-result protection, and idempotent retries.
- Do not create passing states by changing internal storage or mirror Markdown layout/internal call order in tests.
- Use small reproducible fixtures in automation. Keep the actual eight-document acceptance materials and personal records out of Git by default.
- Separately replay fixed teaching scenarios: notation, key prerequisites, future knowledge, repeated difficulty, explicit depth, and skipping, all within the same mainline. Program success does not establish teaching quality.
- Make a recorded real Luna call when available; otherwise demonstrate fallback and state the tested limits. Registering a task is not successful model execution.
- Report automation, material coverage, host integration, teaching replay, and failures separately.

## Out of Scope

Obsidian compatibility/export/sync; dedicated UI; public plugins; multi-user accounts; an always-on service; automatic paid API fallback; a universal document parser; mandatory test passing before advancing; automatic mastery for unanswered questions.

## Further Notes

The private GitHub repository contains the confirmed specification and six implementation tasks. Work uses one integration branch, small test-driven steps, and a final standards/spec review. Consider plugin packaging after acceptance.
