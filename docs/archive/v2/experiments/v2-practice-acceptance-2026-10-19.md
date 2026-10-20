# V2 section practice acceptance (2026-10-19)

Implementation #13 prepares current-concept practice after mainline completion. Prefer source questions, explicitly label teacher-created alternatives, and separate questions from hints/steps/solutions. Record actual learner answers separately; only completed, format-valid teacher assessments enter evidence.assess. Viewing solutions, requesting hints, and retrying after feedback count as assisted work. Deferral retains pending work without mastery upgrades. Learners advance without a passing gate; return from an accepted supplement first.

Course/model-host tests cover persisted questions after reopen, source metadata, wrong-answer needs_work, assisted versus independent evidence, no pass without outcome, late assessments preserving deferrals, and host shutdown rejecting new model work. An idempotent completion scan repairs interruption between completion and practice archival.

## Real channel replay

Used an independent synthetic photoelectric-effect course, leaving quantum-v1 unchanged. Requested gpt-6.1-sol / medium through the configured CLI provider, serially without contention.

| Request | Completion | Result |
|---|---:|---|
| Generate from source containing an answer | 5.4 s | Source-linked question without answer leakage |
| Submit "doubling intensity doubles maximum kinetic energy" | 8.1 s | needs_work; identifies confusion between intensity and photon energy |
| Request a full solution | 15.3 s | Kmax=hν-W, single-photon conditions, electron-count/photocurrent distinction |
| Submit correct reasoning | 8.6 s | passed, but hinted evidence rather than independent mastery |

Raw output: ignored `work/v2-acceptance/practice-live/results.json` and `evidence.json`. This is one functional replay, not a performance promise. It preceded the shared record_user=false patch; actual practice answers always had separate records, and machine requests no longer create artificial learner interactions after that patch.

The browser module offers questions, free help selection, answers, deferral, and next-section controls while preserving drafts/position across updates. Integrated browser evidence is recorded separately; static code is not browser acceptance.
