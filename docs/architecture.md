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

`guided_learning/api.py` dispatches `op` requests to `core`, `sources`, `curriculum`, `teaching`, `evidence`, `background`, `streaming`, `branches`, `practice`, `preparation`, `preferences` and `annotations`. Each call is one `BEGIN IMMEDIATE` transaction on the course database. The Codex skill uses these through the `guided-learning` command (`--course <name>` resolves inside the course library, `--workspace` takes any folder); their names and semantics are a stable contract documented in `guided_learning/skill/references/`, which `guided-learning setup` copies to `~/.agents/skills/guided-learning`. The host calls the same operations and keeps no state of its own besides worker threads.

## Host (`guided_learning/server/`)

- `host.py` — `Host` owns one workspace: takes the single-host lease, marks turns left `running` by a crash as `interrupted`, and runs every model turn through `start_turn` / `pause_turn` / `resume_turn`. Each turn attempt runs in its own thread; runner events become `stream.event` operations, and the `EventBus` publishes `delta`, `turn` and `changed` events.
- `features.py` — the four features, each a class with optional `prompt(turn, context)`, `before_start(request)` and `on_complete(turn)`:
  - `Navigation`: concept previews (including source material the course plan set aside for the section) and exact-revision source views (Markdown text, PDF page PNG, original PDF). It also delivers pending explanations: a mainline lesson in a section with due explanations is asked to give them in full, and they are resolved when that lesson completes.
  - `Questions`: side questions, the `<teaching-decision>` protocol, foundation supplements, return to the mainline.
  - `Practice`: exercise generation, hints/steps/solutions/assessment, deferral, entering the next section.
  - `Preparation`: idle-only preparation of the next section; foreground requests pause it.
- `prompts.py` — every instruction sent to a model. Changing wording here changes teaching behavior.
- `app.py` — the FastAPI routes, the loopback Host/Origin guard, the 1 MiB body limit, and static files. `Courses` holds the course library root and the one `Host` currently open; switching courses closes the old host (pausing its turns and releasing its lease) before opening the next. Routes reach the open course through `ActiveHost`, so they do not track switches, and the SSE `EventBus` is shared across switches. A watcher thread polls a read-only fingerprint of each course's `course`, `sources` and `curriculum` records (`library.fingerprint`) and publishes `changed` with scope `library`, plus scope `state` when the open course changed, so edits Codex makes from outside reach open tabs.
- `guided_learning/library.py` lists library courses read-only through operations; `guided_learning/commands.py` implements `setup`, `open`, `stop` and `courses`. `setup` installs the skill, writes the library's `AGENTS.md` (only replacing one it wrote itself), adds a launcher and prints the `codex://new?path=` project link. `open` starts `guided_learning.web --record` detached and reuses it while `.throughline/host.json` in the library points at a live host.

Rules the host enforces: one running mainline lesson at a time; side questions run alongside it unless the learner pauses it; preparation starts only when nothing else runs; partial text never becomes an interaction or evidence.

## Teacher (`guided_learning/codex.py`, `server/settings.py`)

`CodexRunner` drives `codex app-server`. `TeacherSettings` keeps the Codex model and reasoning effort per user and builds a runner for each turn, so a change in Teacher settings applies to the next request. See ADR 0002.

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | Course, position, curriculum, session, pending explanations, turns, questions, practice, preparation, settings; 409 `no_course` before a course is open |
| GET | `/api/library` | Library root, open course and a summary of each course |
| POST | `/api/library/open` | Open a library course by name (publishes `changed` with scope `course`) |
| POST | `/api/shutdown` | Stop a host started by `guided-learning open` |
| PUT | `/api/preferences` | Save the course interface/teaching language and invalidate stale preparation |
| GET | `/api/events` | SSE: `delta`, `turn`, `changed` |
| POST | `/api/lessons` | Start a mainline lesson (enters the first concept if there is no position) |
| POST | `/api/turns/{id}/pause`, `/resume` | Pause, or regenerate as a new attempt |
| GET | `/api/concepts/{id}/preview` | Overview, prerequisites, sources and set-aside material, without moving the position |
| GET | `/api/sources/{source}/{revision}/{unit}?format=image\|pdf` | Exact source revision; Markdown responses include the whole document for the reader |
| POST | `/api/questions`, `/api/questions/{id}/choice`, `/return` | Side questions and supplements |
| POST | `/api/questions/{id}/replies` | Follow up in the same side question; accepts `id`, `question`, and optional `selection` |
| POST | `/api/practice/generate`, `/api/practice/tasks/{id}/{action}` | Exercises and help |
| POST | `/api/sections/next` | Enter the next route section |
| POST | `/api/preparation/retry` | Retry failed preparation |
| GET/PUT | `/api/settings` | Codex model and reasoning effort |
| POST | `/api/annotations` | Save a learner annotation (highlight, note or bookmark); `/api/state` lists them |
| PUT/DELETE | `/api/annotations/{id}` | Edit an annotation's note, or delete it |

The browser cannot call domain operations directly; there is no generic operation passthrough.

## Interface (`web/`)

`lib/store.svelte.ts` holds one reactive copy of `/api/state`, applies SSE deltas to running turns, and refetches after `changed` events. `lib/markdown.ts` renders sanitized Markdown with KaTeX and turns `[Source id / unit]` citations into source buttons, patching only changed blocks so streaming keeps selections and scroll. Before a course is open, and from **Courses** in the top bar, `Library` lists the courses and links each course action to a new Codex chat (`codex://new?prompt=…&path=<library>`); opening a course reloads the page so the store starts clean. Components map to the page: `TopBar`; `Library`; `RouteRail`; `ConceptPage` (goal, next step derived from the section's lessons and practice, questions saved for the section, `UnitOverview`, `Lesson` with `TurnControls`, `Composer`, `Practice` with `Exercise`, `NextSection`, `Preparation`, `EarlierHistory`); `SidePanel` (`Questions` with `QuestionThread`, `SourceViewer` with `SourceList`, `PdfReader` and `MarkdownReader`, and `Notes`); `SelectionAsk` (Highlight, Note and Ask on a selected passage), `CitationPeek`, `SettingsDialog`, `Shortcuts`. `PdfReader` uses pdf.js (`lib/pdf.ts`), loaded only when a PDF is first opened; it renders pages near the viewport and a selectable text layer. `lib/highlight.ts` paints asked passages and learner highlights with the CSS Custom Highlight API, so lesson and reader DOM is never modified.

Learner annotations are never part of a prompt snapshot or prompt (ADR 0005).

## Adding behavior

- A new kind of model work: add a feature class (or extend one) in `features.py`, its text in `prompts.py`, a route in `app.py`, and any durable records as domain operations.
- Tests: `tests/test_web*.py` drive `Host` directly or through `support.host_client`; `web/tests/*.spec.ts` drive the built UI against fixture courses in `tests/*_fixture.py`.

Language preferences are domain operations (`preferences.view` / `preferences.save`) in the course workspace. Each stream attempt freezes its language alongside its source snapshot. The host emits a preference change notice so connected interfaces refresh their labels without rewriting saved teaching content. Preparation fingerprints include language.

Side questions have a creation timestamp; older records fall back to the original stream start time. The interface shows newest questions first. `branch.reply` appends an idempotent reply (`id` is the branch ID, `reply_id` identifies the reply, with `question` and optional `selection`) without creating another branch or changing the mainline restore point. Earlier answers must be complete. Each reply is a normal pausable/resumable stream, with completed question/answer history frozen in its prompt snapshot. Follow-ups keep the original supplement and pending-explanation decisions; they do not run the branch decision protocol again.

Practice separates learner answers and teacher feedback visually and renders Markdown/LaTeX in both. Unfinished exercises from other sections are initially collapsed. Hints give one cue; key steps provide a symbolic plan, leaving results to the learner; full solutions remain explicit. Assessment considers cumulative learner attempts and accepts correct assisted answers without requiring paraphrasing. Evidence provenance still distinguishes assisted completion from independent work.

If a follow-up was saved before its answer stream could start, the interface retries the same reply ID rather than adding another reply. Failed or interrupted practice assessments show the saved submission and offer to restore it to the editor, including after reload and when earlier feedback exists. Learner answer line breaks are retained; selected display formulas keep display delimiters.
