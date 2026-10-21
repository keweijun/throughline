# Course import, reproduction, and review

## Local course and audit materials

Paths relative to the project root:

| Path | Purpose |
|---|---|
| `work/course-inputs/quantum/<material-name>/` | Stable copies of eight PDFs plus Markdown, MinerU JSON, and supplementary images |
| `work/courses/quantum-v1/` | Official usable workspace with a candidate route awaiting review and no learning records at import |
| `work/courses/quantum-v1/import-requests.jsonl` | Ten public API requests: course creation, eight source registrations, route save |
| `work/courses/quantum-v1/audit/` | Full block-level candidate map, source hashes, original reconnaissance, seven-page checks, import summary, and coverage report |
| `work/courses/quantum-import-check/` | Separate replay-check workspace, not learner progress |

Official sources use physical PDF pages starting at `page-1`. Markdown and cropped images are private supplements rather than thousands of duplicated coverage entries. Markdown lines, zero-based MinerU page indexes, and PDF page numbers are distinct. Full block information remains in audit; current concept links contain only brief topics, content types, review flags, and audit pointers.

These private files are ignored by Git. Cloning does not download course materials. Runtime copies are already inside the local project; historical original paths in audit are provenance only.

## Replay the local import

Run from the repository root in PowerShell with a new workspace name. Each request uses a separate CLI process and stops on failure:

```powershell
$courseImportTarget = 'work/courses/quantum-import-replay'
$coursePython = '.\.venv\Scripts\python.exe'
$courseImportFile = 'work/courses/quantum-v1/import-requests.jsonl'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Get-Content -LiteralPath $courseImportFile -Encoding utf8 | ForEach-Object {
    $_ | & $coursePython -m guided_learning --workspace $courseImportTarget
    if ($LASTEXITCODE -ne 0) { throw 'Course import stopped; inspect the error before continuing.' }
}
'{"op":"curriculum.coverage"}' | & $coursePython -m guided_learning --workspace $courseImportTarget
'{"op":"session.resume"}' | & $coursePython -m guided_learning --workspace $courseImportTarget
```

The replay file retains absolute input paths and content hashes; it reproduces the import while those copies remain unmoved and unchanged. Do not merely substitute JSON paths while retaining old references: normalized paths affect source IDs and content changes affect revisions. On another computer or in another directory, register again and rebuild links from returned IDs/revisions.

After real learning begins, do not overwrite the active route with the candidate import file. Review in a new workspace first. Confirm major reordering and preserve stable concept IDs and evidence.

## Create another course

1. Copy user-provided originals into a stable course-specific input directory, retaining the originals. Run `course.init`, register each `source.register {path}`, check status, and inspect units with `source.read {source_id}`.
2. The teacher builds `concepts`, `route`, and `coverage`, using returned `source_id, revision, unit_id` for every link. See [course operations](../.agents/skills/guided-learning/references/course-operations.md) and [curriculum operations](../.agents/skills/guided-learning/references/curriculum.md).
3. Reading success only establishes text extraction. Mark missing images, unclear formulas, failures, or undecided meaning as `needs_review` with reasons. Keep dispositions for deferred in-scope content even if exercises do not test it.
4. Submit the candidate map through `curriculum.save`; retain a UTF-8 JSON request for `--request` replay. Inspect all units and `semantic_completeness` in `curriculum.coverage`, then confirm the overall route.
5. Record real interactions, position, and evidence only when actual teaching begins. Route import does not create taught/mastered records.

## Review priorities for this course

All 231 pages have candidate dispositions; 190 explicitly need review for formulas, images, diagrams, or sparse text. Seven-page spot checks checked specific issues without upgrading whole pages to verified. Review upcoming original pages first, then the rest of the course.

- PS01 Q1(2) includes numerical comparison with lectures; Q4 defines the average scale as `1/<r^-1>`, not `<r>`.
- PS01 Q6/Q7 and PS02 Q1 have transcription errors adding absolute-value bars around whole expressions; teach from the PDF.
- PS02 Q2 part 3 allows numerical integration; Q4 retains first-order, second-order, and closure-approximation requirements.
- Explain box lengths `a/L`, frequencies `nu/omega`, `mu` for reduced mass versus dipole moment, and perturbation order versus state index in context. Notation entries remain source-linked candidates.
- The 23 exercise requirements count independent subquestions across 11 main questions. Two unnumbered proofs become Q6.a/Q6.b. PS02 Q4.3 first/second-order requirements remain one subquestion with both retained in detail.

Submit `verification:verified` with a substantive `verification_note` only after the relevant check. Source verification, taught content, and independent answering are separate records.
