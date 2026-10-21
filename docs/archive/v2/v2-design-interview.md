# Second design round: field feedback, course overviews, and companion panel

Status at interview start: discussion only. Record design/facts without implementation changes, real-course writes, services, or prototypes. Later sections record subsequent authorization and progress.

## Field evidence

User-specified chat `01a13495-be40-74a3-bddd-30cc34e53310`, whose title translates as "Start the quantum-v1 course," reported roughly two-minute waits for full explanations, faster small questions, unclear position, and a desire for a big picture before major units and possibly a UI.

Tool summaries for ten recent turns showed median total duration about 142.5 s, range 88.5–227.6 s; recorded command runtimes totaled about 1.3–2.7 s per turn. Total turn time is not first-character latency, and command totals omit some image/model/tool round trips, so precise attribution is unavailable.

Entering new content involved reading/viewing several original pages. Full answers were first saved as script text and then output in the final reply. Segment measurements were needed to establish the effect on waiting.

## Confirmed preferences

- Preserve full explanation length; shortening is not the default speed strategy.
- Preserve quick responses to small questions.
- Initially use a companion panel alongside native Codex chat; potentially move chat into a custom interface later.
- Panel and teacher share official workspace state, preserving the ownership decision.
- Discuss first rather than directly fix; continue the design process through ask-matt.
- Q1: default to course contents plus a short flowchart for the current major unit; expand detailed dependencies on demand.
- Q2: clicking a concept previews only, without moving teaching position.
- Q3: accept main teacher, independent preparation agent of the same model tier, and Luna consolidation. Plan the unit and pipeline preparation by section; the look-ahead window and unavailable-preparation behavior still needed selection.
- Q4: accept the main teacher taking over necessary preparation when the buffer is unready, with visible status. Auxiliary failures must neither block teaching nor eliminate source checks.
- Explicitly test whether preparation actually accelerates the teacher; do not assume it works.

## Suggestions not yet confirmed at this stage

- Show a one-screen overview at a major unit's start and retain current position during learning.
- Accepted role direction: main teacher sets unit goals, learner constraints, and route; independent same-tier preparation agent checks sources, derivations, examples, exercises, and uncertainties; Luna may index/consolidate candidates. The teacher reviews preparation rather than repeating every check each turn. Not yet run.
- Unit planning should produce section-level materials rather than lock in a final chapter script; the teacher handles live questions and depth.
- Suggested pipeline: create the overview and prepare section one initially, then roll ahead 1–2 sections during teaching, with one active preparation agent initially. Preparation writes separate material, never position/mastery. Relevant route/source changes require re-review.
- Distinguish preparation ready from studied/mastered. Keep reusable material on route switches and stop or deprioritize irrelevant tasks.
- Reduce duplicate full-answer generation; automatic capture from desktop chat remained unverified.
- Prioritize structure, goals, sources, and unfinished work in the panel, with future learning-client reuse.

## Design tree and frontier

1. Companion panel accepted initially; contents/local flow and preview-only clicks decided.
2. Preserve explanation length while improving waiting. Unit planning, section preparation, same-tier independent execution, and teacher takeover accepted in direction. Core hypothesis: can checked preparation shorten delivery while preserving length and quality? Read-only exploration must establish lifecycle, authoritative-answer capture, and availability before promising background behavior.
3. After those decisions, use an interface prototype for layout questions, then specifications/tasks. No prototype was authorized at that point.

## Technical boundaries

Official [App Server documentation](https://learn.chatgpt.com/docs/app-server) describes custom-client sessions, streaming, approvals, and related integration. It does not guarantee seamless takeover of desktop conversations or migration of all desktop plugin capabilities.

Read-only exploration in `work/v2-feasibility.md` found background operations only for note consolidation: no preparation cache, pipeline scheduler, or automatic desktop-final capture. [Subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) describes concurrency/model selection, but typical flows collect results before a combined reply. Local lifecycle after a parent turn, new user message, stop, or app exit was untested. An isolated experiment was needed before promising a preparation buffer across user turns; discussion alone started none.

## Preparation benefit comparison

The user authorized screening. Three A/B pairs used the current CLI custom provider with gpt-6.1-sol / medium; see experiments/preparation-latency-2026-10-13.md. All six scripts passed independent content checks. Aggregate teacher-stage time fell 22.4%, but one pair was 15.4% slower, and total work increased when preparation was included. This was an initial signal, without a pipeline, cache, or UI implementation.

Pre-execution principles:

Separate preparation benefit from subagent lifecycle; test the benefit before building scheduling for an ineffective optimization.

- A: same goal, learner background, and original materials; prepare and teach as before.
- B: same conditions plus checked, concise, traceable preparation, retaining original-source access.
- Fix teacher model, reasoning, content target, length requirement, and recording. Do not simultaneously change UI, model, length, or persistence.
- Screen a few different section types using alternating order and fresh contexts. Small initial samples determine whether repetition is worthwhile, not stable acceleration.
- Measure first useful content when reliable, full delivery, tool/image calls, length, and available usage. Preparation messages are not teaching. Mark missing first-content timing rather than inventing it.
- Record preparation time/usage separately and distinguish cold-start cost from ready-preparation foreground waiting.
- Compare concepts, formulas/conditions, continuity, and sources. Shortening or omitting checks is not a valid speedup.
- Record mixed/failing outcomes when repeated image reading/rederivation or larger packages add overhead. Do not default to a complex pipeline without improvement.
- Test duplicate full-answer generation later as a separate variable.

## Single-output experiment (executed)

After separate user authorization, an isolated App Server client compared double model output with one reply recorded by the host, without changing preparation or production. See experiments/single-output-2026-10-14.md.

Across three pairs, Single delivered the first 200 final-answer characters in 31.5 s on average versus Double's 90.0 s; aggregate full time fell 37.1% despite slightly longer Single scripts. All six passed independent content checks, and saved text matched authoritative items byte-for-byte. The small sample supports prioritizing capture without a stable percentage promise. Native-chat adaptation, crash recovery, and real-course transactions remained unverified; no companion UI or pipeline was implemented at this stage.

## Post-experiment discussion (2026-10-14)

The user accepted continuing single-output design and explicitly allowed teaching to move to a new UI if native Codex could not support it. The earlier companion-only preference stopped being a hard constraint, without immediately deciding migration or authorizing production.

Pending choices were teaching-entry priority, side questions during generation, and overview timing/default expansion. Preview-only clicks, workspace ownership, and lesson length remained fixed. Native mirroring was not promised without feasibility evidence.

## Confirmed direction and next frontier

The user accepted all recommendations:

- Q1: prioritize an independent learning UI integrating streaming, orientation, and autosave, replacing the earlier companion-only priority. Still design-stage.
- Q2: ordinary questions during generation become branches while mainline generation and reading position remain; provide explicit pause/reteach. Difficulties affecting later explanation may pause/adjust, with automated/user-control boundaries still pending.
- Q3: show a short major-unit overview automatically, then start section one without confirmation. Retain position summaries and brief cross-day reminders.

Next independent choices: section progression gates, automatic pause for prerequisite gaps, and preparation look-ahead. Native-capability migration and concurrency still required technical validation.

## Confirmed learning pace

The user accepted Q4–Q6 recommendations:

- Q4: learners advance sections; grouped practice allows answers, follow-ups, or continuation with pending work. Background preparation does not switch screens. Taught does not mean mastered.
- Q5: teachers suggest missing-foundation supplements and learners choose whether to switch. Explicit pause acts directly. Confirmed errors stop the incorrect explanation and are corrected.
- Q6: default one section ahead, one active preparation task, foreground teaching/questions first, main teacher takeover if unready. Keep the unit plan without preparing whole chapters by default; measure contention/performance.

Next frontier: hint/answer presentation and shared reading space for sources/branches. Production implementation had not begun.

## Confirmed practice and source interaction (2026-10-19)

Q7–Q8 recommendations accepted: show questions first with answers hidden, freely request hints/steps/solutions, never treat viewed answers as mastery, and allow deferral without blocking. Use left navigation, central learning, optional right assistance; sources and branches share the initially closed right area, with a narrow-screen drawer and stable reading position.

Started `work/prototypes/learning-flow.prototype.html` to answer whether branches, supplements, and deferred practice preserve continuity. It used simulated content and memory-only state, without models or course writes. Three clickable walkthroughs cover question/return, prerequisite gaps, and separate preparation/learning state. It was a logic prototype, not final UI. Real-source jumps, streaming concurrency, selected-text questions, and cross-session recovery were unimplemented. Await user feedback before conclusions and prototype-branch preservation; do not describe it as a validated product.
