# V2 acceptance: independent learning interface

Date: 2026-10-19 (America/Los_Angeles). Specification #9; tasks #10–#15. Program behavior, real models, and content checks are reported separately; one success is not a speed or learning-effect guarantee.

## Program and browser

Final code commit 2b5192d passed 69 Python tests (49.5 s) and five browser suites. Later 40bc5fc only merged acceptance documentation. Coverage includes state/evidence, exact source revisions, streaming save and duplicate/late events, pause/recovery, branches, practice, preparation invalidation, foreground priority, and fallback. The original three browser suites cover navigation/sources/responsiveness, sentence/formula selection and return, and preparation status. The manual defer/advance walkthrough below was separate from those automated suites. New regressions cover older-lesson identity, interrupted supplements, and unfinished exercises across sections. Both independent review tracks were fixed and rechecked; see [review](review-v2.md).

The real quantum course's original PDF image was checked in-browser; preview left bohr-spectrum position unchanged. Screenshot: `work/v2-acceptance/navigation-pdf/actual-source-page.png`. See [selection checks](experiments/v2-branch-selection-2026-10-19.md) for formula selection and scroll restoration.

## Final real end-to-end flow

Used a full copy of `work/courses/quantum-v1` at `work/v2-acceptance/final-flow/course`, HTTP host port 8771, configured gpt-6.1-sol / medium. The original course was unchanged; its database SHA-256 matched before copying and after teaching.

The public HTTP entrypoint started this copy's first UI Bohr lesson. Completion hooks automatically generated practice, then idle scheduling prepared wave-particle. No completion state or preparation text was injected manually.

| Stage | Measurement | Result |
|---|---|---|
| First 200 lesson characters | 38.473 s | Substantive unit overview, not a preparation message |
| Full lesson | 77.693 s; 3529 characters | Authoritative text saved once |
| Save call | 0.0052 s | Transaction commit not timed separately |
| Automatic exercises | 10.975 s | Two explicitly self-created questions |
| Next-section preparation | 31.941 s; 1511 characters | Ready without learner interaction or mastery evidence |

Times come from host stream events rather than screen painting; characters include Markdown/formula syntax. Practice/preparation durations are per request, not cumulative from lesson start. Startup preparation was preempted by teaching, then rescheduled to completion. Its paused record remains and was not hidden as success.

In the real browser, "Do later" on question one followed by "Enter next section" left that question deferred and moved the mainline to wave-particle without requiring a pass. After stopping and reopening with the README CLI command, the browser retained the new goal, earlier lesson, and deferred question. Official evidence matched initialization, with no independent mastery added. Question two remained in the database; this initial walkthrough did not prove it was accessible across sections. That visibility gap was then fixed and independently checked.

Exactly one assistant interaction equaled authoritative lesson text character-for-character. Raw records, snapshots, single-save checks, and evidence comparisons remain under ignored `work/v2-acceptance/final-flow/`. Reopening rescheduled further preparation as part of lifecycle testing, outside the timing sample above.

## Other real-model evidence

- [Streaming/recovery](experiments/v2-stream-delivery-2026-10-19.md): real pause, retained partial text after reopen, successful complete regeneration. Regeneration does not continue seamlessly at a character offset.
- `work/v2-branch-live/report.json`: submitted a local notation question while mainline was running; both later completed. Decisions included brief answers, later depth, and prerequisite suggestions. The local question took about 7.12 s. Metadata does not count as substantive first-200-character teaching content.
- `work/v2-acceptance/browser-supplement.json`: asked a prerequisite question, accepted the supplement, and returned. Suggestion: 238 visible characters, about 20.55 s; supplement: 2871 characters, about 44.45 s. Goal position was unchanged on return.
- [Practice replay](experiments/v2-practice-acceptance-2026-10-19.md): wrong reasoning received needs_work; a correct answer after viewing the full solution recorded hinted rather than independent evidence.
- [Preparation/priority](experiments/v2-preparation-2026-10-19.md): the same small question took 5.902 s without preparation and 5.928 s while preparation was preempted. One pair cannot establish a stable difference or always-on execution after exit.

## Teaching content review

Paragraph-level review of the final Bohr lesson found a concrete overview asking why hydrogen has specific spectral wavelengths. Its steps connect stationary states/angular-momentum quantization to radii/levels and then transitions/spectra, linking photon relations and later wavefunctions. It includes classical stability, fixed-nucleus/nonrelativistic conditions, Coulomb centripetal balance, angular-momentum quantization, radius/energy derivations, the negative-energy reference, unequal level spacing, absorption/emission signs, the Rydberg relation, series limits, and model limitations. The 4→2 example correctly gives 2.55 eV / about 486 nm. It distinguishes circular paths from modern orbitals and retains pending/unverified source limits.

Two answer-free questions cover transition calculations, energy comparisons, and discrete spectra. The first reused the worked 4→2 example, useful for reproduction but insufficient alone for transfer; the second compared 5→2 and 5→1. This repetition prompted an instruction to check recent worked examples and prefer new situations or values.

After fix 8d2d877, an independent real practice replay copied the initial course and used public interaction.record to retain the actual lesson/source_refs as a historical teaching fixture, without presenting it as fresh lesson reasoning. Only one real practice request ran; preparation scheduling was disabled to isolate it. It completed in 18.726 s with two answer-free self_created questions: a 5→3 transition (energy, wavelength, series), and n=2 versus n=3 ionization thresholds for a 2.00 eV photon. Neither repeated 4→2. Physics checks give about 0.9671 eV and 1282 nm in the Paschen series; thresholds are 3.40 and about 1.511 eV, so only n=3 is energetically ionizable by that photon. Raw result: `work/v2-acceptance/exercise-transfer/result.json`. One replay supports the prompt change without guaranteeing all future transfer questions or establishing learner mastery.

These are output correctness/coverage checks, not real-learner effectiveness experiments. Existing review records do not establish fresh verification of all 231 pages; teachers must progressively review the candidate map.

## Installation and distribution

A wheel was built from the working tree. Initial --no-build-isolation failed because setuptools.build_meta was missing; normal isolated build succeeded without changing model credentials. The archive includes 36 static assets, 20 WOFF2 fonts, and marked/DOMPurify/KaTeX scripts, styles, licenses, and manifest. Client rendering needs no CDN. This establishes packaging, not a clean-machine installation replay.

[README](../README.md) provides the real-course launch command; [usage](learning-ui.md) covers dependencies, course paths, pause/reopen, lifecycle, and failures. Course materials/personal progress stay local and outside Git/wheels.

## Remaining limits

Personal local use only: no multi-user accounts, remote deployment, post-exit service, or native Codex chat mirror. A small number of real requests establish channel/workflow availability without a latency SLA. Teacher assessment can still be wrong; tests cannot establish that errors or unknowns never occur. Candidate/unverified source status remains; completed UI implementation does not mean completed knowledge coverage.

The final five suites are navigation, branches, preparation, branch_recovery, and practice_continuity. Final runs had no expected-disconnect exception traces; invalid-PDF fixture parser messages are expected. Regression checks cover unfinished exercise visibility, all-history toggles, supplement pause/recovery, and separate historical-source/current-mainline identities.
