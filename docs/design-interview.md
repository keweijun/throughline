# Personal guided-learning workflow: design interview

Status: design choices confirmed; awaiting confirmation of the overall proposal. Implementation has not begun.

This continues the earlier interview, archived under docs/archive/initial-design/. The project is now at F:\Projects\codex-guided-learning; the former directory retains only a historical copy.

## Confirmed decisions

| ID | Decision |
|---|---|
| Q1 | Personal use. |
| Q2 | First priority: cross-document teaching continuity and coverage checks. |
| Q3 | Flag prerequisite gaps; continue if requested, retaining pending checks without mandatory unlocking. |
| Q4 | Local background services and additional model APIs are acceptable. |
| Q5 | All lecture content is in teaching scope, with voluntary skips; Q16 defines coverage granularity, while the route and need determine depth. |
| Q6 | Reorder teaching across documents by prerequisites and retain sources. |
| Q7 | Teach a continuous section, then group practice; no default quiz after every concept. |
| Q8 | V1 stays in chat to validate teaching quality; decide on a dedicated interface later. |
| Q9 | No additional restrictions on using learning materials with external models; this preference does not establish that an upload occurred. |
| Q10 | Resume automatically after brief branches; after long explanations, name the resume point and wait. |
| Q11 | Give enough explanation for current use, mark limits, and bind the full derivation to a later node for proactive review; expand immediately when explicitly requested. |
| Q12 | Use different examples or short conceptual bridges for repeated difficulties; ask before major rearrangement. |
| Q13 | Prioritize revisiting old questions, adapting explanations to difficulties, and cross-document notation/concept comparisons. |
| Q14 | Define sections by complete goals, potentially across lectures and multiple turns; practice at natural closure. |
| Q15 | Identify the obstacle and give minimal necessary hints; provide a full demonstration on request without counting independent completion. |
| Q16 | Register definitions, conclusions, derivations, and examples by page in the background; present concepts in the foreground. Merge duplicates with sources, expose parsing failures, and ask the user to review the overall route and disputed choices. |
| Q17 | V1 may pause when the learner leaves and resume later. Save original exchanges and mainline position promptly; consolidation may wait. No always-on background requirement. |
| Q18 | Prefer Codex Luna. If unavailable, defer optional consolidation and continue teaching; no automatic paid API fallback. |
| Q19 | V1 delivers a generic skill, independent course workspace, and helpers; no dedicated UI, persistent service, or plugin packaging yet. |
| Q20 | Separate taught, hinted, independent, and delayed-retest evidence, with self-reports separate. Revisit deferred items when needed, at agreed nodes, or section review. Resume with a short recap, without a mandatory test. |
| Q21 | The course workspace is the sole official state. No Obsidian compatibility, export, or sync. Recheck affected concepts after source changes while retaining evidence. Confirm major reordering. Preserve failed background tasks and prevent stale overwrites. |
| Q22 | Build a complete coverage map from six lectures and two exercise documents; validate wavefunctions → eigenstates → projection, branch routing, later review, recovery, and continued teaching without Luna. |

A new core requirement is route-aware depth selection for local questions while preserving the mainline. The user also wants to explore behavior closer to a human teacher.

## Established capabilities and limits

At the time of the interview, session tools could select gpt-6-luna for a subagent. Official documentation described model/reasoning selection and delegation requested by applicable skills: https://learn.chatgpt.com/docs/agent-configuration/subagents.

At that stage Luna had not been tested and no background service existed. Session subagents could not be treated as reliable services after a reply or application exit. API model names and quotas were not assumed interchangeable with Codex.

## Confirmed teaching behavior

- Route-aware question answering considers current necessity, later placement, repeated difficulty, and explicit depth requests.
- Preserve the mainline goal, explanation step, next step, and unfinished practice before branching.
- Give minimal intuition for future concepts, bind the question to its node, and revisit it on arrival.
- Resume after brief branches; retain the resume point and wait after long explanations.
- Perform local remediation autonomously for repeated difficulty; ask before major reorganization.
- Prioritize old-question review, alternative explanations, and cross-document notation comparisons.

## Implementation constraints

Separate taught, self-reported understanding, answered, and independently passed evidence. Practice at section ends, give minimal hints, and resume with a short recap rather than a compulsory test. The main teacher decides depth immediately; Luna may extract evidence, locate materials, or propose note updates without delaying every small question.

## Interview convergence

No decision frontier remains. V1 boundaries are in v1-spec.md. Begin implementation after the user confirms shared understanding of the overall proposal.

After confirming these boundaries, summarize the proposal for shared understanding; proceed to implementation if no new branches arise. Choose the simplest reversible technical approach that satisfies the agreed rules rather than turning every internal detail into another interview question.
