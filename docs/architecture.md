# Architecture

Three layers, each depending only on the one below:

```
web/ (Svelte UI, built into guided_learning/web_dist)
   │  HTTP + one SSE stream, loopback only
guided_learning/server/   Host, features, prompts, FastAPI routes
   │  execute(workspace, {op, ...})
guided_learning/*.py      domain operations (also the Codex skill's JSON CLI)
   │
course.sqlite3 + sources/<id>/<revision>   the course workspace (ADR 0001)
```

## Domain operations

`guided_learning/api.py` dispatches `op` requests to `core`, `sources`, `curriculum`, `teaching`, `evidence`, `background`, `streaming`, `branches`, `practice` and `preparation`. Each call is one `BEGIN IMMEDIATE` transaction on the course database. The Codex skill uses these through `python -m guided_learning`; their names and semantics are a stable contract documented in `.agents/skills/guided-learning/references/`. The host calls the same operations and keeps no state of its own besides worker threads.

## Host (`guided_learning/server/`)

- `host.py` — `Host` owns one workspace: takes the single-host lease, marks turns left `running` by a crash as `interrupted`, and runs every model turn through `start_turn` / `pause_turn` / `resume_turn`. Each turn attempt runs in its own thread; runner events become `stream.event` operations, and the `EventBus` publishes `delta`, `turn` and `changed` events.
- `features.py` — the four features, each a class with optional `prompt(turn, context)`, `before_start(request)` and `on_complete(turn)`:
  - `Navigation`: concept previews and exact-revision source views (Markdown text, PDF page PNG, original PDF).
  - `Questions`: side questions, the `<teaching-decision>` protocol, foundation supplements, return to the mainline.
  - `Practice`: exercise generation, hints/steps/solutions/assessment, deferral, entering the next section.
  - `Preparation`: idle-only preparation of the next section; foreground requests pause it.
- `prompts.py` — every instruction sent to a model. Changing wording here changes teaching behavior.
- `app.py` — the FastAPI routes, the loopback Host/Origin guard, the 1 MiB body limit, and static files.

Rules the host enforces: one running mainline lesson at a time; side questions run alongside it unless the learner pauses it; preparation starts only when nothing else runs; partial text never becomes an interaction or evidence.

## Teacher (`guided_learning/codex.py`, `server/settings.py`)

`CodexRunner` drives `codex app-server`. `TeacherSettings` keeps the Codex model and reasoning effort per user and builds a runner for each turn, so a change in Teacher settings applies to the next request. See ADR 0002.

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | Course, position, curriculum, session, turns, questions, practice, preparation, settings |
| GET | `/api/events` | SSE: `delta`, `turn`, `changed` |
| POST | `/api/lessons` | Start a mainline lesson (enters the first concept if there is no position) |
| POST | `/api/turns/{id}/pause`, `/resume` | Pause, or regenerate as a new attempt |
| GET | `/api/concepts/{id}/preview` | Overview, prerequisites and sources, without moving the position |
| GET | `/api/sources/{source}/{revision}/{unit}?format=image\|pdf` | Exact source revision; Markdown responses include the whole document for the reader |
| POST | `/api/questions`, `/api/questions/{id}/choice`, `/return` | Side questions and supplements |
| POST | `/api/practice/generate`, `/api/practice/tasks/{id}/{action}` | Exercises and help |
| POST | `/api/sections/next` | Enter the next route section |
| POST | `/api/preparation/retry` | Retry failed preparation |
| GET/PUT | `/api/settings` | Codex model and reasoning effort |

The browser cannot call domain operations directly; there is no generic operation passthrough.

## Interface (`web/`)

`lib/store.svelte.ts` holds one reactive copy of `/api/state`, applies SSE deltas to running turns, and refetches after `changed` events. `lib/markdown.ts` renders sanitized Markdown with KaTeX and turns `[Source id / unit]` citations into source buttons, patching only changed blocks so streaming keeps selections and scroll. Components map to the page: `RouteRail`, `ConceptPage` (goal, overview, lessons, composer, practice, next section), `SidePanel` (questions, and `SourceViewer` with `PdfReader` and `MarkdownReader`), `CitationPeek`, `SettingsDialog`, `Shortcuts`. `PdfReader` uses pdf.js (`lib/pdf.ts`), loaded only when a PDF is first opened; it renders pages near the viewport and a selectable text layer.

## Adding behavior

- A new kind of model work: add a feature class (or extend one) in `features.py`, its text in `prompts.py`, a route in `app.py`, and any durable records as domain operations.
- Tests: `tests/test_web*.py` drive `Host` directly or through `support.host_client`; `web/tests/*.spec.ts` drive the built UI against fixture courses in `tests/*_fixture.py`.
