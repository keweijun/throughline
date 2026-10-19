# V2 acceptance execution plan

Baseline: the integration branch starts at V1 commit deeea3e; all 33 existing tests passed on 2026-10-19. Specification #9, tasks #10–#15. This is a plan, not a passing report.

## Automation and course state

For each task, write failing tests at the agreed public boundary before implementation. Run the full existing/new suite at the end, checking idempotency, late events after pause, disconnect, reopen, route switches, and stale preparation. Do not manufacture acceptance state by writing directly to the database.

## Real channel

Use the configured Codex channel with gpt-6.1-sol / medium. Preserve credentials and avoid new paid fallbacks. Run traceable isolated real calls. Run baseline comparisons serially and label concurrent workloads separately.

1. Full lesson: save request, completion status, first-200-character time, full time, character count, and record equality.
2. Pause/recovery: pause a running request, keep partial text unfinished, then regenerate a valid completion; late content must not pollute a new attempt.
3. Mainline/branch concurrency: submit a local question while the mainline generates; check separate records, answer scope, and restore point.
4. Next-section preparation: validate real output, fallback, and version invalidation; compare foreground-question latency with/without preparation and report sample counts.

## Browser

Use the actual service and a real course copy. Check course contents, position, overview, preview isolation, original pages, selected-passage questions, accepting/declining supplements, pause/return, hints/solutions/deferral, and voluntary next-section entry. Check desktop and narrow layouts, stable scrolling during growth, and position retention across auxiliary views.

## Teaching and data

Create an isolated read-only SQLite backup of the existing quantum course and copy source snapshots. Do not modify the original or record demonstrations as independent mastery. Keep pending source verification visible; UI integration does not establish full-material review.

Report program, real-model, browser, teaching, performance, and unresolved results separately. Earlier single-output results inform the approach without guaranteeing stable performance.
