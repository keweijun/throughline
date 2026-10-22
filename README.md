# Guided Learning

Guided Learning is a local study app for learning from several PDFs and Markdown documents as one course. Codex organizes the materials into a source-linked route. The browser app then teaches with unit overviews, streaming lessons, questions about selected passages, original-page reading, practice, and a saved place to resume.

The teacher makes instructional judgments from the materials. The program validates state and references; it never decides on its own that you have understood something.

Each course workspace owns its route, source snapshots, position and learning evidence. Everything runs on your computer and uses your configured Codex CLI as the teacher. The interface and new teaching default to English; Simplified Chinese is available from the language selector, and imported materials keep their original language.

## Install

You need the [Codex CLI](https://learn.chatgpt.com/docs/codex/cli), signed in, and Python 3.10 or newer. Paste this into Codex:

```text
Install Guided Learning for me: run `uv tool install --upgrade "codex-guided-learning[pdf] @ git+https://github.com/keweijun/codex-guided-learning"` (if uv is missing, use `pipx install --force` with the same quoted package, or `python -m pip install --user --upgrade` as a last resort), then run `guided-learning setup` and show me its output.
```

Codex installs the package (no Node.js needed), copies the `guided-learning` skill into `~/.agents/skills/`, and creates your course library. Paste the same prompt again to update.

## Use it from Codex

You never need to type a command; ask Codex:

- `$guided-learning create a course called quantum from these files: …` copies the files into the course library, registers them and builds the route.
- `$guided-learning open quantum` starts the learning interface in the background and opens it in your browser. Codex asks for permission because the interface keeps running after the command and runs Codex for lessons.
- `$guided-learning add these files to quantum: …`, `review the pages that still need review in quantum`, `stop the learning interface`.

The interface opens on **Your courses**, the course library: every course with its sources, sections, review backlog and current section. Open one to study; **Courses** in the top bar switches between them. Creating and changing courses stays in Codex, which does the reading and judging; the library shows the prompts to paste.

Courses live in `~/.local/share/guided-learning/courses` (`%LOCALAPPDATA%\guided-learning\courses` on Windows; set `GUIDED_LEARNING_HOME` to move everything). Each course is one folder; to move a course, stop the interface and copy its folder. Extraction alone does not verify formulas, images or teaching coverage, so the library shows what still needs review.

## Commands behind the prompts

```sh
guided-learning setup                 # install or update the Codex skill
guided-learning open [course] [--no-browser] [--port 8765]
guided-learning stop
guided-learning courses               # JSON list of the library
echo '{"op":"course.status"}' | guided-learning --course quantum
```

`guided-learning-web --workspace <folder>` still serves a course outside the library in the foreground; `--port`, `--model` and `--effort` work as before.

## Choose the teacher model

Lessons, answers and feedback are written by `codex app-server` on this computer, using your existing Codex sign-in and configuration. Open **Teacher settings** (the model name in the top bar) to set the model and reasoning effort; leave the model empty to use your Codex default. Settings live in your user config directory (`~/.config/guided-learning/settings.json`, or `%APPDATA%\guided-learning\settings.json` on Windows), never in a course folder, and apply to new requests only. See [ADR 0002](docs/adr/0002-codex-is-the-only-teacher.md).

## Read sources

Citations in lessons and exercises show the cited text on hover. Clicking one opens the built-in reader beside the lesson: PDFs open at the cited page with selectable text, zoom and page controls; Markdown notes open at the cited line. Select text in either reader to ask a side question about it. Drag the panel edge to resize it.

## Course operations

The skill is bundled in the package at [guided_learning/skill/](guided_learning/skill/SKILL.md). It reads and updates course workspaces through the operation entry point, which accepts JSON from a request file or standard input:

```sh
echo '{"op":"course.init","title":"My course"}' | guided-learning --course demo
echo '{"op":"session.resume"}' | guided-learning --workspace work/courses/demo
```

Success returns `{ok:true,result:...}`; failure returns `{ok:false,error:...}` with a nonzero exit code. Use `--request request.json` for long text or formulas. Position-changing operations `position.save` and `mainline.enter` need a unique `request_id`; reuse it only for retries.

## What the course workspace keeps

- PDF and Markdown sources with revision snapshots, reading issues and exact locations.
- Cross-document concepts, prerequisite routes, notation and exercise mappings, with validated references, cycles and coverage dispositions.
- The teaching mainline and side questions, with route-aware answer depth, foundation supplements and pending explanations.
- Section practice with taught, self-reported, hinted, independent and retest evidence kept separate.
- Deferred items, revisited when due without a mandatory quiz.

Background preparation runs only while the host is running. Course materials and databases stay in the course library (or local `work/` for development) and are never tracked by Git.

## Development

- [Architecture](docs/architecture.md): modules, HTTP API, live events and how to extend them.
- [Using the interface](docs/learning-ui.md): pause, regenerate, side questions, practice, recovery and troubleshooting.
- [Creating and reviewing a course](docs/course-import.md): what the skill does when it builds a course, and how to check or replay it.
- [Domain glossary](GLOSSARY.md) and [decisions](docs/adr/).

From a checkout, install in development mode and run the tests:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[pdf]"        # Windows: .venv\Scripts\python.exe
.venv/bin/python -m unittest discover -s tests
.venv/bin/guided-learning setup                     # copy this checkout's skill to Codex; rerun after editing it
```

Frontend work happens in `web/` (Svelte 5, Vite, TypeScript):

```sh
cd web
npm install
GL_HOST=http://127.0.0.1:8765 npm run dev   # hot-reloading UI against a running host
npm run check                               # type check
npm run build                               # writes guided_learning/web_dist (commit the result)
npx playwright test                         # browser tests against disposable fixture courses
```

The project uses GitHub Issues; engineering instructions start at [AGENTS.md](AGENTS.md). Project code is licensed under [MIT](LICENSE); bundled dependencies retain the licenses in [third-party notices](THIRD_PARTY_LICENSES.md).
