# Next-section preparation integration — 2026-10-19

Issue #14. Preparation is optional, internal material tied to current route/source versions. The idle host prepares only the next concept and allows only one physically active preparation worker. New foreground mainline, sidequestion or practice work pauses preparation immediately without waiting for model shutdown. The scheduler waits for old preparation process exit before another preparation. Material is injected when its concept becomes current; absent, failed or stale material leaves the teacher responsible for necessary source checks. Preparation is not appended to learner/teacher interaction history and never changes mastery or position.

The host runs preparation only while open. Shutdown stops the scheduler; startup reconciles interrupted streams and jobs orphaned before stream launch. Failed jobs wait for explicit retry. Route/source changes invalidate both running and ready material. The fingerprint uses curriculum, current source revisions/status and target context; historical source revisions are not repeatedly hashed. Normal learner interactions do not invalidate preparation.

## Real model checks

Isolated synthetic two-section course, identical source text and the same short photon-energy question in both conditions. Requested model `gpt-6.1-sol`, medium reasoning, configured CLI provider, real Codex App Server transport. One sample per condition, sequential. No original course state modified. This measures foreground priority overhead, not the benefit of already prepared content.

| Condition | First substantive text | Completed reply | Save operation |
|---|---:|---:|---:|
| Without preparation running | 4.689 s | 5.902 s | 0.0013 s |
| Preparation active, preempted by question | 4.604 s | 5.928 s | 0.0016 s |

Both replies correctly explain that fixed frequency leaves single-photon energy unchanged while intensity changes photon flux. Replies are short, so a first-200-character metric is not applicable. The 0.026 s difference in total duration is not evidence of a stable performance gain or penalty.

The interrupted preparation process exited (2.900 s total lifetime, including the initial two seconds before the question); a subsequent automatic preparation completed in 17.652 s process wall time. Its material included goals, prerequisite connection, formula conditions, an example, exercise suggestions and explicit source uncertainty. The next-section teacher received the exact prepared text and completed a separate threshold-frequency question: first substantive text 6.557 s, full reply 9.110 s. This was an injection smoke test, not a paired latency comparison. Session history contained exactly the two user questions and two teacher answers, no internal preparation requests or replies.

Raw prompts, transport events, runtime files, snapshots and results are retained under ignored `work/v2-prep-live/` in the main project. Initial live run used merge commit `b52f0ec`; subsequent small changes added orphan recovery, avoided hashing historical sources, and corrected status panel placement. These do not change the measured model prompt or priority policy.

## Automated and browser checks

- Initial full suite: 61 tests passed; after merging immutable-source changes, 12 focused stream/web/preparation tests passed.
- Five preparation tests cover no history/mastery/position mutation, source and route invalidation, automatic scheduling/preemption/injection, failed-job fallback/no retry storm/shutdown, and startup recovery after enqueue-before-launch crash.
- Headless Chromium: readiness visible separately from learning state, internal preparation absent from history, and no narrow-screen horizontal overflow introduced by the status panel.
- Failure, route-change and orphan scenarios are deterministic transport-boundary tests, not claims of real provider failure recovery timing. Only one small real latency pair was measured; no exit-survival or concurrency SLA is promised.
