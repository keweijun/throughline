# #10: single streaming lesson and recovery validation

2026-10-19. Used an isolated course copy without changing real quantum-v1 state.

## Automated checks

Added course-operation, real JSON-RPC subprocess, and local HTTP boundary tests:

- Atomically record an official assistant interaction only for authoritative final_answer text and successful turn completion; repeated events do not duplicate it.
- Partial output, pause, and disconnect are unfinished. Late events/old attempts cannot overwrite current state; missing sequence numbers are rejected.
- Commentary-only replies and EOF do not masquerade as lessons.
- Full-section regeneration after pause is idempotent; older/newer mainlines cannot overlap.
- An OS file lock prevents a second host from taking the same course and marking live work interrupted.
- HTTP Host/Origin checks restrict loopback and reject cross-site requests; arbitrary source files are not exposed.

## Real configured channel

Used configured Codex App Server, explicit gpt-6.1-sol / medium, read-only sandbox, never approval. Input came from bohr-spectrum in a copied quantum course, with linked lecture text, pending flags, route, and recent history.

| Measurement | Result |
|---|---|
| Text before pause | 223 characters |
| Paused turn first 200 | 11.26 s |
| Full text after reopening | 3259 characters |
| Complete turn first 200 | 12.25 s |
| Complete turn full time | 45.39 s |
| Interaction write, excluding commit | 0.0068 s |

After pause, waiting for model exit, host shutdown, and reopening, paused state/partial text remained. User regeneration produced a complete new attempt. Official interaction matched authoritative text exactly; retrying the original request did not regenerate or duplicate records. The lesson covered Bohr assumptions, radius/level derivations, spectra, and examples, explicitly retaining pending source limits.

Reproduction: ignored `work/v2-acceptance/stream-delivery/check.py`, `result.json`, `final.md`, and independent `course/`. Metrics span host initiation to persistent stream events; first 200 counts characters rather than native UI painting.

## Limits

- Pause cannot freeze server reasoning. Regeneration starts a new model turn and retains earlier partial text for inspection; it is not seamless continuation at an offset.
- One real sample establishes availability, not speed. This run preceded removing the full coverage ledger from prompts; current prompts use route summaries/current sources.
- The initial UI rendered safe text; later tasks integrate Markdown/math, navigation, and branches.
- save_s measures the interaction call; commit is in total API duration but not separately timed.

## Integration correctness additions

- stream.start freezes original source text, precise revision/unit references, route summary, and session context in one transaction. Prompts and completion records use that snapshot. Regeneration retains its goal/sources; old attempts retain provenance. Start a new lesson to use updated materials.
- A regression changes source content/mappings before generation and checks that prompt text and final provenance retain the original revision.
- Twenty 64 KB cross-site POSTs reproduced Windows connection resets caused by unread bodies. Reading ordinary bounded bodies before rejection now returns 403 reliably. Retain Host/Origin checks, a 1 MB limit, three-second read timeout, and chunked-request rejection.
- All 60 tests passed after integration (37.9 s), including these regressions. No additional real-model call in this round.
