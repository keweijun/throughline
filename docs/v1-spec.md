# Personal cross-document guided learning: V1 proposal

Status: interview decisions confirmed; overall proposal awaiting final confirmation. This describes intended behavior rather than implemented functionality.

## Goal and deliverables

Use Codex chat for personal, coherent cross-document teaching, coverage checks, and route-aware question answering. Deliver a generic guided-learning skill, independent course workspace, and necessary helpers.

Validate teaching quality first. V1 excludes Obsidian compatibility/export/sync, a dedicated learning UI, public plugin distribution, and an always-on service. Future extensions remain possible without adding their dependencies now.

## Materials and route

- Start with six quantum lecture documents and two exercise documents, building a complete coverage map.
- Locate definitions, key conclusions, derivations, and examples by page in the background; present concepts in the foreground.
- Merge shared concepts while preserving all sources and additional details; map notation differences.
- Organize cross-document routes by prerequisites rather than file order alone.
- Give every content item an explicit disposition. Expose parsing failures without claiming coverage of failed pages. The user reviews the overall route and disputed choices.
- Recheck affected concepts when materials change, preserve answer evidence, and ask before major route changes.

## Teaching and branches

- Organize sections around complete learning goals, potentially across sources and turns, with grouped practice at the end.
- Choose answer depth using necessity for current understanding, future placement, repeated difficulty, and explicit user requests.
- Answer small questions briefly and return to the mainline; explain key concepts fully; name the resume point and wait after long explanations.
- For later knowledge, provide enough for current use with clear limits, link the full explanation to a later node, and revisit proactively. Expand immediately on explicit request.
- Save a mainline restore point; a side question does not automatically become the main goal.
- Use new examples or short bridges for repeated difficulties; ask before major rearrangement.
- The learner controls advancement: flag prerequisite gaps, then allow continuation with the gaps retained as deferred items.

## Practice and learning evidence

- Group practice at section ends; identify specific obstacles and give minimal necessary hints after errors.
- Demonstrate full solutions on request without recording independent learner completion.
- Record taught, self-reported, hinted, independent, and delayed-retest evidence separately.
- Revisit deferred items when needed, at agreed nodes, or during section recap, without reminders every turn.
- Resume with a brief recap and restore the task without a mandatory exam.

## State and model roles

- The course workspace is the sole official learning state; generic skill instructions stay separate from course data.
- Persist actual interactions, current goals, restore points, pending explanations, and answer evidence, rather than relying only on a continually rewritten summary.
- The main teacher explains and makes depth/instructional decisions immediately, without waiting for an auxiliary model on every small question.
- Prefer a Codex gpt-6-luna subagent for batch consolidation, source location, and candidate evidence extraction.
- When unavailable, retain and defer optional work; teach from current state and recent interactions.
- Tasks may pause on departure and resume later; no guarantee of continued execution after closing chat or the app.
- Background updates reference original evidence; retries do not double-count progress and stale results cannot overwrite newer state. Keep storage and validation simple and reversible.
- V1 does not automatically switch to an additional paid API. Future API use is acceptable, but providers, budgets, and spending rules are not configured.

## Acceptance

Check the coverage ledger for all eight documents, then validate the wavefunctions → eigenstates → projection teaching chain.

| Scenario | Passing behavior |
|---|---|
| Local notation question | Explain what is needed and return to the mainline without unrelated chapters. |
| Key foundation question | Explain concepts needed by the current material rather than mechanically advancing. |
| Future knowledge question | Address the immediate issue, retain a full-explanation node, and revisit on arrival. |
| Repeated difficulty | Use an alternative explanation or short bridge while preserving the goal. |
| Skip or request a solution | Respect the choice while preserving unverified status. |
| Interrupt and reopen | Restore the correct goal, position, unresolved questions, and evidence. |
| Luna unavailable | Teaching continues; consolidation tasks remain, without lost or regressed records. |
| Read failure or changed materials | Expose gaps without silently completing them; retain existing evidence on update. |

Notes count, output length, and one model self-assessment do not establish success. Scripts check state and coverage consistency; fixed scenarios and actual learner experience validate teaching behavior. Measure latency rather than promising a speedup in advance.

## Implementation order

1. Design minimal state and helpers; verify save/resume, coverage checks, and duplicate-update handling.
2. Write the skill and references, including route context and branch handling.
3. Add optional Luna support and unavailable-host recovery.
4. Build the real-material coverage map and replay acceptance scenarios; fix issues before ongoing use.

See design-interview.md for detailed choices and root GLOSSARY.md for terminology.
