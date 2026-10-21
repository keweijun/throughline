# V2 web extension contract

Run `python -m guided_learning.web --workspace <existing-course> --port 8765`.
Local loopback only, configured Codex CLI provider/model; optional `--model` and `--effort`.

## Python

`guided_learning.web.create_server(workspace, host='127.0.0.1', port=8765, runner=None, model=None, effort='medium')` returns HTTPServer with `.app`.

`LearningApp.operation(request)` uses transactional course API; `.snapshot()` returns `{course,position,sources,curriculum,session,turns}`.
`start_turn({id,concept_id,prompt,channel})`; allowed channels mainline/sidequestion/practice/preparation.
`pause_turn(id)` rejects late output immediately and asks owned model process to interrupt.
`resume_turn(id,request_id)` regenerates whole reply with a new attempt (not continuation), preserving previous partial text in `attempts`.
`.wait(id,timeout)` joins current attempt and returns durable turn.

Optional modules `guided_learning.web_navigation`, `web_branches`, `web_practice`, `web_preparation` expose `register(app)`:
- `app.routes[(HTTP_METHOD, '/api/feature/...')] = handler`; POST handler receives body; GET receives full URL for query parsing. Return JSON, or `(bytes, content_type)` for safe source viewing.
- `app.prompt_hooks.append(hook)` where `hook(turn, context)` returns additional prompt string.
- `app.completion_hooks.append(hook)` where `hook(turn)` observes a completed durable reply; callback runs worker thread, do not mutate another worker's state.
- New transactional operation module must be added to `api.MODULES`.

Raw user request is `stream-user:<id>`, completed assistant `stream:<id>` (idempotent). Partial, failed and paused streams never create assistant interactions. State fields: id,concept_id,prompt,channel,status,attempt,text,final_text,sequence,started_at,metrics,attempts. Terminal statuses completed/paused/failed/interrupted. Resume regenerates entire lecture; label it honestly. No automatic mastery or mainline advancement.

## HTTP

GET /api/state; POST /api/operation (existing public course operations only; stream.* is reserved for host lifecycle).
POST /api/turns; POST /api/turns/:id/pause; POST /api/turns/:id/resume `{request_id}`.
GET /api/turns/:id/events is SSE of durable snapshots (no stream IDs needed; reconnect retrieves current state). UI never scrolls to bottom automatically.

## Browser features

Place JS under `guided_learning/web_static/feature-<name>.js`. Host discovers them via /features.json. Each exports async `setup(app)`; no central loader edit needed.
`app.api(path, body?)`, `.operation(request)`, `.refresh()`, `.state`, `.startTurn(request)`, `.pauseTurn(id)`, `.resumeTurn(id)`.
`app.events` EventTarget: `state` detail whole snapshot; `turn` detail updated turn.
`app.elements` contains navigation/overview/practice/auxiliary DOM nodes. `.showAuxiliary()` and `.hideAuxiliary()` toggle auxiliary.
Use textContent or safe rendered markup; model output is untrusted. Preserve nodes and reading positions across state events.
