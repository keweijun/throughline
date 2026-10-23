# A FastAPI host with one turn engine, and a built Svelte interface

The v2 host grew as a stdlib HTTP server with a patched route dictionary, four `web_*` extensions registering prompt, start and completion hooks, a polling SSE endpoint per turn, and six browser feature scripts that each polled the server. Adding behavior meant touching several loosely ordered hook lists.

The host is now `guided_learning/server/`: a FastAPI app with typed request bodies, one `Host` that runs every model turn (lesson, side question, supplement, practice, preparation) through the same worker and lifecycle, explicit feature classes in place of hook lists, all model-facing text in `prompts.py`, and one `/api/events` stream that pushes deltas and change notices. The interface is a Svelte 5 + TypeScript app in `web/`, built into `guided_learning/web_dist` and committed, so learners still need no Node.js and no network access for the interface.

Unchanged: the course workspace remains the only learning state (ADR 0001); domain operations and the JSON CLI used by the Codex skill keep their names and semantics; the loopback-only, same-origin, bounded-body rules stay; existing courses open without migration. ADR 0004 later extended the host to serve a course library, one open course at a time.

The cost is two runtime dependencies (FastAPI, Uvicorn) and a developer-only frontend build step. Contributors changing the UI must run `npm run build` and commit the output.
