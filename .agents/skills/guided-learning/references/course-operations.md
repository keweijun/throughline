# Course operations

From the repository root run `python -m guided_learning --workspace <course-directory> --request <request.json>`. Install `python -m pip install -e ".[pdf]"` for PDF extraction. The request file is UTF-8 JSON; omit `--request` to read JSON from stdin. An installed package can run outside the repository. Exit 0 returns `{ "ok": true, "result": ... }`; exit 1 returns `{ "ok": false, "error": { "code": ..., "message": ... } }`.

## Requests

- `{"op":"course.init","title":"Quantum"}` creates a course; reopening via init preserves the existing title and state.
- `{"op":"course.status"}` returns `course`, `position`, and `sources`.
- `{"op":"source.register","path":"/absolute/path/slides.pdf"}` returns `source` containing stable `id`, normalized `path`, SHA256 `revision`, `status`, `verification`, and `errors`. Repeat after a file changes. Missing files stay visible with a failed latest registration; an earlier revision remains readable. A successful registration means the attempt was recorded, not necessarily that extraction succeeded.
- `{"op":"source.read","source_id":"src-..."}` returns the latest available snapshot with `units`, `status`, `errors`, and `verification`; pass `revision` to retrieve a previous snapshot. Each unit has stable within-revision `id`, `locator` and `text`. Markdown uses `{ "line": 1 }`, PDF uses `{ "page": 1 }`. PDF empty/image-only pages are `needs_review`.
- `{"op":"position.save","position":{"goal":"Understand normalization","progress":"Introduced probability density","next_step":"Normalize the example"}}` saves a minimal mainline position object.

`verification: pending` means formulas, images and page mapping have not been independently checked. Source units are extraction units, not a completed coverage ledger. A Markdown line must not be presented as a PDF page.

## Storage and extension contract

The workspace contains `course.sqlite3` and `sources/<source-id>/<sha256>` byte snapshots. Use operations instead of editing the database. Source identity follows normalized absolute path; moving a source registers a new identity. Keep a stable input location for revisions.

Python callers use `guided_learning.execute(workspace, request)`; validation errors raise `OperationError` with `.code`. Each request holds one SQLite `BEGIN IMMEDIATE` transaction. An exception rolls it back. Operation modules export `OPERATIONS = {"operation.name": handler}`; add the module name to `guided_learning.api.MODULES`. Handlers take `(store, request)` and return JSON-serializable results. `store.get(namespace, key, default=None)`, `put(namespace, key, value)`, `list(namespace)` and `delete(namespace, key)` read/write JSON documents; reserve a separate namespace for each feature. `store.db` is available when relational constraints are needed. Handlers must not commit or close the shared transaction.

Core namespaces: `course` (`metadata`, `position`), `sources` (key: source ID), `source_revisions` (key: `<source-id>:<revision>`). Preserve old snapshots and user learning evidence when building on source changes. Reading a snapshot may use a cached earlier revision even when the newest registration failed; consult source status as well.
