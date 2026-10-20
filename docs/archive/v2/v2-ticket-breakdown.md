# V2 implementation tasks

2026-10-19. Specification and validation boundaries confirmed; the user accepted this breakdown and implementation is complete. Draft numbers below are distinct from GitHub Issue numbers.

1. **Real teaching, single save, and interruption recovery.** No prerequisite. Open an existing course, start real teaching from a minimal page, stream/save it, and restore after refresh/reopen. Expose cancellation and unfinished replies. Check authoritative text equality, idempotent retries, partial-output status, real pause/recovery, and first-content/full latency. Reuse the course entrypoint and add only necessary adapters.
2. **Navigation, unit overviews, and sources.** Depends on 1. Read the official route; show course contents, current goal, and local flow. Show an overview at first teaching and a resume reminder across sessions. Concepts preview only; citations open verifiable original pages. Check position isolation, explicit missing locations, narrow windows, and stable scrolling.
3. **Side questions, supplements, and mainline return.** Depends on 1. Ask about selected sentences/formulas with route context. Run ordinary branches alongside teaching; supplements need acceptance, explicit pause acts directly, and return restores the original position. Check real concurrency/contention, late events after pause, no branch advancement, and brief/deep/supplement scenarios. Auxiliary views can be built independently of navigation.
4. **Section practice, hints, and voluntary advancement.** Depends on 1. Show questions first, offer progressive help or full answers, and use existing evidence operations for real answers. Defer while keeping work pending; learners advance. Check that viewing answers/deferring does not imply mastery, pending work survives reopen, hints remain distinct from independent work, and passing is optional.
5. **Next-section preparation and foreground priority.** Depends on 3 and 4. Prepare one section ahead with at most one active task, based on route and learner advancement. Show preparation separately from mastery; the teacher handles missing preparation. Check actual calls, source/route invalidation, fallback, stale-result isolation, and immediate-question latency with/without preparation. No unverified always-on promise.
6. **Full learning flow and continuity acceptance.** Depends on 2–5. Use the quantum course for overview → lesson → question → source → practice → continue → reopen. Fix integration seams and separately report program, real integration, teaching, and performance. Preserve lesson length/concepts; report distributions and failures; check narrow auxiliary views and reading positions through actual operation.

Task 1 is first; 2, 3, and 4 have no hard dependencies on each other. Each task owns its tests and demonstration; task 6 does not absorb omitted basic checks. Establish real dependencies at publication. The draft itself did not authorize production implementation.

## Published (2026-10-19)

The user confirmed this breakdown. Parent specification: #9.

| Draft | GitHub Issue | Prerequisites |
|---|---|---|
| 1 | #10 | None |
| 2 | #11 | #10 |
| 3 | #12 | #10 |
| 4 | #13 | #10 |
| 5 | #14 | #12, #13 |
| 6 | #15 | #11, #12, #13, #14 |

All tasks were labeled ready-for-agent. Implementation and integrated acceptance of all six are complete; see acceptance-v2.md.
