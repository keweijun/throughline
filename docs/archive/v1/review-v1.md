# V1 code review: standards and specification

Baseline: main at `ce0e0a1`; scope: V1 integration branch. Two independent agents reviewed standards and specification. Findings were fixed together, then rechecked by the original reviewers. Final functional review point: `6b02923`; later changes only update acceptance records.

## Standards

No violations of AGENTS.md, domain terminology, or the state-ownership ADR. One optional maintenance suggestion concerned repeated CLI assertions across five suites with differing error-exit checks. A small shared helper now handles those calls while preserving scenario-specific assertions. No remaining standards findings after recheck.

## Spec

Four issues were reproduced through public operations, fixed, and covered by regressions:

| Priority | Issue | Fix and recheck |
|---|---|---|
| P1 | Old checkpoint retries overwrote newer progress | Require stable request_id; retries return current position and original result without restoring old position; reject conflicting content. |
| P2 | Assessment lost original source revisions after updates | Snapshot source units/revisions on interactions and reference original answer/feedback sources; unknown historical provenance stays unknown. |
| P2 | Deferred items could not be acknowledged at the agreed target | Accept real user confirmation on the original or agreed target concept; continue rejecting unrelated concepts. |
| P2 | Answers beyond recent history were inaccessible publicly | Add interaction.read by ID for original text/source auditing without enlarging every-turn context. |

The specification reviewer reran original and negative scenarios in a fresh isolated workspace. All four passed without detected regressions. All 33 tests passed; independent teaching replay is recorded separately.

Remaining findings: Standards 0, Spec 0. Full semantic review, real learner outcomes, and speed benchmarks remain explicit validation limits rather than passing claims.
