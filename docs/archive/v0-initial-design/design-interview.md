# Personal guided-learning workflow: initial design interview

Status: interview in progress; the overall proposal is not yet confirmed. Do not start implementation. This is a historical record; see the current design interview for subsequent decisions.

## Confirmed decisions

| ID | Decision | Meaning |
|---|---|---|
| Q1 | Personal use | V1 serves the user rather than public distribution or multiple users. |
| Q2 | Prioritize cross-document guided learning | Validate teaching continuity and coverage first; speed and UI remain later goals. |
| Q3 | Warn, then allow continuation | Explain prerequisite gaps, continue when requested, and retain later checks without a mandatory passing gate. |
| Q4 | Services and APIs acceptable | Local background services and additional model APIs are allowed in principle; provider, budget, data scope, and architecture remain undecided. |

The earlier suggestion to begin with a skill and expand into a plugin remains a candidate, not an accepted choice.

## Design tree

- Audience: personal (decided); initial course and migration scope pending.
- Primary value: continuity and coverage (decided). This round covers content depth, cross-document integration/order, and lightweight evidence checks. State, gap filling, and acceptance depend on those answers.
- Advancement: learners may skip (decided); revisit timing comes later.
- Runtime: local services/additional APIs acceptable (decided). This round considers Codex versus dedicated UI and external-model data scope. Budget, model roles, triggers, and recovery follow later.
- Packaging: skill/plugin/MCP combination depends on earlier decisions.

## Questions for round two

- Q5: lecture coverage scope and depth.
- Q6: precedence between lecture order and prerequisites when they conflict.
- Q7: default understanding checks.
- Q8: Codex's role in the learning interface.
- Q9: materials that may be sent to external models.

No technical choice yet warrants an ADR. Record user decisions first rather than presenting suggestions as accepted architecture.
