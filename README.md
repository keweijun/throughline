# Guided Learning

Personal cross-document guided learning. A local course workspace keeps your sources, learning route, teaching mainline and actual learning evidence. A local web app teaches from it: streaming lessons with unit overviews, side questions about any passage, original source pages, section practice and background preparation of the next section. The teacher can be any OpenAI-compatible model or your local Codex CLI.

The teacher makes instructional judgments from the materials. The program validates state and references; it never decides on its own that you have understood something.

Documentation and the interface are in English. Teaching defaults to English; ask for another language in a lesson request or question when you want one. Imported materials and existing course records keep their original language.

## Install

Requires Python 3.10+. From the repository root:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[pdf]"        # Windows: .venv\Scripts\python.exe
.venv/bin/python -m unittest discover -s tests
```

The built interface ships inside the package (`guided_learning/web_dist`), so learners need neither Node.js nor internet access for the interface itself. Markdown, math and fonts are bundled.

## Open a course

```sh
.venv/bin/python -m guided_learning.web --workspace work/courses/quantum-v1
```

Open http://127.0.0.1:8765. The host listens on loopback only and owns the course while it runs; press Ctrl+C to stop it. The course must already exist; see [course import](docs/course-import.md) to create one.

Options:

- `--port 8766` when 8765 is taken.
- `--provider ID` and `--model NAME` pick a provider and model for this run only, without changing your saved choice.
- `--config PATH` uses a different provider settings file.

## Choose the teacher model

Open **Model settings** (the model name in the top bar). Two kinds of provider are supported:

- **Local Codex CLI** (the default): runs `codex app-server` on this computer with your existing Codex configuration. Leave the model empty to use your Codex default.
- **OpenAI-compatible**: any server that implements `/v1/chat/completions` with streaming, such as OpenAI, OpenRouter, Ollama, LM Studio or vLLM. Set a base URL and model name; **Load available models** reads the server's `/models` list.

API keys can be stored in the settings file or read from an environment variable you name (for example `OPENAI_API_KEY`). Settings live in your user config directory (`~/.config/guided-learning/providers.json`, or `%APPDATA%\guided-learning\providers.json` on Windows), saved with owner-only permissions. They are never written into a course folder and keys are never sent to the browser. Changing provider affects new requests only. The app never switches provider on its own. See [ADR 0002](docs/adr/0002-openai-compatible-teacher-providers.md).

## Use the Codex skill

Open this project in Codex and invoke `$guided-learning`. The skill is at [.agents/skills/guided-learning/SKILL.md](.agents/skills/guided-learning/SKILL.md). It reads and updates the same course workspace through the operation entry point, which accepts JSON from a request file or standard input:

```sh
echo '{"op":"course.init","title":"My course"}' | .venv/bin/python -m guided_learning --workspace work/courses/demo
echo '{"op":"session.resume"}' | .venv/bin/python -m guided_learning --workspace work/courses/demo
```

Success returns `{ok:true,result:...}`; failure returns `{ok:false,error:...}` with a nonzero exit code. Use `--request work/request.json` for long text or formulas. Position-changing operations `position.save` and `mainline.enter` need a unique `request_id`; reuse it only for retries.

## What the course workspace keeps

- PDF and Markdown sources with revision snapshots, reading issues and exact locations.
- Cross-document concepts, prerequisite routes, notation and exercise mappings, with validated references, cycles and coverage dispositions.
- The teaching mainline and side questions, with route-aware answer depth, foundation supplements and pending explanations.
- Section practice with taught, self-reported, hinted, independent and retest evidence kept separate.
- Deferred items, revisited when due without a mandatory quiz.

Background preparation runs only while the host is running. Course materials and databases stay in local `work/` and are not tracked by Git. To move a course, stop the host and copy its whole directory.

### Prepared local quantum course

`work/courses/quantum-v1` registers six lecture documents and two exercise documents (231 pages) with 45 candidate concepts, 23 exercise subrequirements and eight source-linked notation entries. **It is a candidate coverage map awaiting review**: 41 pages have candidate mappings, 190 explicitly need review, and verification for all pages remains pending.

## Development

- [Architecture](docs/architecture.md): modules, HTTP API, live events and how to extend them.
- [Using the interface](docs/learning-ui.md): pause, regenerate, side questions, practice, recovery and troubleshooting.
- [Domain glossary](GLOSSARY.md) and [decisions](docs/adr/).
- Earlier specifications, reviews and experiments are kept in [docs/archive](docs/archive/).

Frontend work happens in `web/` (Svelte 5, Vite, TypeScript):

```sh
cd web
npm install
GL_HOST=http://127.0.0.1:8765 npm run dev   # hot-reloading UI against a running host
npm run check                               # type check
npm run build                               # writes guided_learning/web_dist (commit the result)
npx playwright test                         # browser tests against disposable fixture courses
```

The project uses GitHub Issues; engineering instructions start at [AGENTS.md](AGENTS.md).
