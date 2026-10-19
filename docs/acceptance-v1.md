# V1 acceptance report

Date: 2026-10-13. Scope: local V1 for GitHub #2–#7. Implementation, tests, and both review tracks are complete; complete semantic coverage and long-term learning effects are not established. See [review-v1.md](review-v1.md).

## Results by evidence layer

| Layer | Measured result | Does not establish |
|---|---|---|
| Program behavior | 33 CLI tests passed, covering sources, routes, branch recovery, evidence, pending explanations, background state, and review regressions | Infallible teaching or learner mastery |
| Actual materials | Eight PDFs / 231 pages registered; 45 candidate concepts, 23 independent exercise requirements, eight source-linked notation entries | Verification of every concept |
| Coverage ledger | 41 mapped pages, 190 needs_review; all 231 pending, zero verified | Semantic completeness or learning completion from mapped status |
| Original-page checks | Primary agent viewed seven PNG pages and recorded formula/question discrepancies | Verification of all 231 pages or all images |
| Teaching replay | 57 final API operations plus 30 wavefunctions → eigenstates → projection operations in an isolated copy, no failures | Long-term learner experience or gains |
| Luna integration | Real gpt-6-luna calls on initial/final versions; final synthetic interactions produced two candidate notes accepted as one task's derived set | Consolidation of real personal records or execution after chat closes |

## The eight documents

The six lecture filenames use the original local-language title for Physical Chemistry H1, followed by the dates below. Original filenames remain unchanged in private inputs.

| Document | Pages |
|---|---:|
| Physical Chemistry H1, 20260914 | 42 |
| Physical Chemistry H1, 20260915 | 43 |
| Physical Chemistry H1, 20260921 | 36 |
| Physical Chemistry H1, 20260922 | 34 |
| Physical Chemistry H1, 20260928 | 36 |
| Physical Chemistry H1, 20260929 | 36 |
| PChemH1_ProblemSet01.pdf | 2 |
| PChemH1_ProblemSet02.pdf | 2 |

Inputs were copied to `F:/Projects/codex-guided-learning/work/course-inputs/quantum`, with eight Markdown files, eight MinerU JSON files, and 463 supplementary JPGs; originals were unchanged. Registration paths are within the project, independent of the original note application. Source hashes match reconnaissance; all eight sources have read status and no extraction errors. This establishes extraction only.

Official course: `F:/Projects/codex-guided-learning/work/courses/quantum-v1`. Its title explicitly flags candidate routes and pending page-level semantic review. **At import, no old personal conversations were imported: zero interactions, empty position, and no evidence for all 45 concepts.** The learner chooses the first teaching point; no completed stages are invented.

Full candidate blocks are in private `audit/quantum-candidate-map.json`. Focused context retains brief page detail, block types, review flags, and audit_pointer. Five actual contexts—wavefunction-born, linear-eigen, completeness, measurement-expectation, box-one-dimensional—had available sources without stale references.

## Limits of visual spot checks

The primary agent viewed PS01 pages 1–2, PS02 pages 1–2, 20260915 page 32, 20260921 page 14, and 20260928 page 4. Findings in `work/visual-check.md` were copied into course audit:

- Original PDFs lack the whole-expression absolute-value bars added by transcriptions in PS01 Q6/Q7 and PS02 Q1.
- Retain PS01 Q1(2)'s numerical comparison, Q4's `1/<r^-1>` definition, and PS02 Q2's numerical-integration permission.
- Explain stationary spatial wavefunctions versus full time phases, normalization denominators in expectations, and box-length notation.

Rendering emitted font warnings; those seven pages were readable. Other pages were not inferred to be correct. All pages remain pending so local checks do not become whole-page certification.

## Teaching replay and discovered defects

An independent teacher agent used real-material context in an isolated simulated course for notation short answers, prerequisite long answers, future concepts, repeated difficulty, explicit depth, continuation, and recovery. Initially, a future q3 asked while q2 was waiting after a long explanation had no way to retain its promised later explanation. Added `deferred.create`, preserving q2's restore point and binding q3 to a later concept. This addresses #4 with two regression tests.

Fixed replay evidence: `work/teaching-replay-fixed/operations.jsonl` and `transcript.md`; 57 CLI operations, zero failures. The primary agent checked:

- Operation 28 creates the future promise; 29–30 preserve q2 waiting and its restore point, with 30 in a new process.
- 31–32 save the actual simulated continuation message before closing the branch.
- 38 surfaces the item at Fourier; 42 remains pending after merely recording the full answer; 43 explicitly resolves it; 46 confirms clearance.
- Repeated difficulty uses a purely imaginary example; explicit depth triggers a full phase-to-momentum explanation.

These are simulated learners, outside the official course, not human learning-effect evidence.

The final version replayed all 57 operations in `work/teaching-replay-final`, adding only stable request_id values required by the updated checkpoint API. All succeeded. Additional checks showed old retries cannot regress position, and historical text/source versions remain readable by ID. Another 30 operations in an isolated official-course copy taught wavefunction representations, eigenfunction identification, orthonormality, and projection coefficients, fulfilling a pending explanation. Only teacher explanations were recorded; no mastery was invented. The primary agent reconfirmed the official course still had empty position and zero real interactions.

## Luna and unavailable-host fallback

`work/luna-smoke-result.json` records the initial real host call; `work/luna-smoke-final-result.json` records the final API call. Both used synthetic exchanges. The final two notes distinguish learner self-report, teacher explanation, and a request not to pose exercises yet. After reference review, they were accepted as one task's derived output without changing evidence or position.

Background tests separately cover retained tasks when unavailable, resume/retry, stale conflicts, and no additional automatic API. Host execution and state-machine tests are separate evidence: enqueue success is not model success. V1 may pause and resume; it has no persistent service.

## Reproduction and private results

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
'{"op":"course.status"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
'{"op":"curriculum.coverage"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
'{"op":"session.resume"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
'{"op":"curriculum.context","concept_id":"wavefunction-born"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/quantum-v1
```

Actual import used public `execute`. The same ten requests were replayed in independent CLI processes into `work/courses/quantum-import-check`, all successfully. Checks reconfirmed 231 pages, 45 concepts, 23 requirements, five contexts, and no official learning evidence. Private results are `audit/import-summary.json`, `coverage.json`, and `import-replay-result.json`. See [import instructions](course-import.md) for a PowerShell replay loop.

## Remaining validation

- Review every concept, formula, and image semantically; the ledger currently preserves uncertainty.
- Evaluate route depth, explanation quality, and latency with actual learner feedback; this round had no latency benchmark.

## Final program and review results

After review fixes at `6b02923`, all 33 tests, skill validation, and diff checks passed. The four specification findings and one optional standards suggestion were handled and independently rechecked by their original reviewers. See [review-v1.md](review-v1.md). No measured speedup or long-term learning-gain conclusion was reached.

Original PDFs, transcriptions, crops, databases, raw replays, and model responses remain in ignored `work/`. Committed artifacts contain generic code, usage instructions, and this report without personal answers.
