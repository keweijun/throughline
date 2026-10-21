# V2 final review and fixes

2026-10-19. Baseline deeea3e; initial integration 7e6748d; fixes 2c01a11 and 2091ede; final code integration 2b5192d.

## Standards

The independent review found no hard engineering-rule violations. Vendor assets matched manifest hashes and retained licenses. It found one P2 correctness issue: cancellation before model thread/turn IDs arrived could leave regeneration waiting for the default 600 seconds.

Initialization, thread creation, and turn creation now support prompt exit and cleanup of owned child processes. Independent recheck passed three transport tests; the finding is resolved.

## Spec

The independent review found two P2 issues: selected historical text was associated with the latest lesson, mixing context/sources; interrupted supplements lacked their own unfinished state and recovery action.

Selected-lesson identity, frozen text, and sources are now separate from current mainline restore/pause targets. Supplements display lifecycle state and support pause, regeneration, and reopen recovery. Independent recheck passed nine branch tests and inspected the browser regressions.

## Integration walkthrough fixes

- Old pending/deferred/needs_work exercises remain visible after section changes; completed exercises are available through all-history view, without evidence changes.
- Collapse preparation/composer panels for saved lessons while retaining current position; historical cards show their concept title.
- Replace blank embedded browser PDFs with local images of exact source snapshots, retaining original PDFs.
- Exercise prompts avoid just-demonstrated questions. One real replay generated new transition and ionization-threshold problems; this does not guarantee all future quality.
- Freeze original sources/references at request start; reject cross-site POST deterministically; suppress expected client-disconnect traces.

## Final validation

All 69 Python tests and five browser regressions passed on the final code. See [acceptance](acceptance-v2.md) for real models, content review, performance samples, original-course protection, and packaged resources. Both review tracks' findings were resolved with no known outstanding items. Review success does not establish infallible models or stable latency.
