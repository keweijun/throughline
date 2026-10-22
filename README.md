# Guided Learning

Guided Learning is a local study app for learning from several PDFs and Markdown documents as one course. Codex helps organize the materials into a source-linked route. The browser app then teaches with unit overviews, streaming lessons, questions about selected passages, original-page reading, practice, and a saved place to resume.

The teacher makes instructional judgments from the materials. The program validates state and references; it never decides on its own that you have understood something.

Your course workspace owns the route, source snapshots, position, and learning evidence. The app runs on your computer and uses your configured Codex CLI as its teacher. The [Codex skill](.agents/skills/guided-learning/SKILL.md) is an optional guide for preparing a course and opening the app. Installing the skill alone does not install the app or include a course.

## First-time setup

Install [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) and Python 3.10+, then clone this repository:

```sh
git clone https://github.com/keweijun/codex-guided-learning.git
cd codex-guided-learning
```

From the repository root, install the app:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[pdf]"        # Windows: .venv\Scripts\python.exe
.venv/bin/python -m unittest discover -s tests
```

On Windows PowerShell, use `py -3 -m venv .venv` and `.\.venv\Scripts\python.exe -m pip install -e '.[pdf]'`. The built interface ships in the Python package; Node.js is needed only for frontend development.

## Prepare a course with Codex

Open this clone in Codex and ask:

> Use `$guided-learning` to build a course from my PDFs and exercises. Show the proposed route and what still needs source review, then open the learning interface when the course is ready.

Provide the paths to stable local copies of your materials and your learning goal. The skill registers sources, saves a course under `work/courses/<course-name>/` by default, and reports the actual course path. You can ask Codex to resume and reopen it later.

**A clone contains no course materials or learning history.** The maintainer's quantum course described in historical documents lives under the ignored local `work/` folder. It is not included in Git or the Python package. Extraction alone does not verify formulas, images, or teaching coverage.

## Open a prepared course yourself

```sh
.venv/bin/python -m guided_learning.web --workspace 'work/courses/<course-name>'
```

Replace `<course-name>` with the name returned by Codex. On Windows, use `.\.venv\Scripts\python.exe` instead. Open the URL printed by the host (normally http://127.0.0.1:8765). The host listens on loopback only and owns the course while it runs; press Ctrl+C to stop it. See [course import](docs/course-import.md) for the underlying operations.

Options:

- `--port 8766` when 8765 is taken.
- `--model NAME` and `--effort LEVEL` pick the Codex model and reasoning effort for this run only, without changing your saved choice.
- `--config PATH` uses a different teacher settings file.

## Choose the teacher model

Lessons, answers and feedback are written by `codex app-server` on this computer, using your existing Codex sign-in and configuration. Open **Teacher settings** (the model name in the top bar) to set the model and reasoning effort; leave the model empty to use your Codex default. Settings live in your user config directory (`~/.config/guided-learning/settings.json`, or `%APPDATA%\guided-learning\settings.json` on Windows), never in a course folder, and apply to new requests only. See [ADR 0002](docs/adr/0002-codex-is-the-only-teacher.md).

## Read sources

Citations in lessons and exercises show the cited text on hover. Clicking one opens the built-in reader beside the lesson: PDFs open at the cited page with selectable text, zoom and page controls; Markdown notes open at the cited line. Select text in either reader to ask a side question about it. Drag the panel edge to resize it.

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

### Maintainer's private local quantum course

The maintainer's ignored `work/courses/quantum-v1` registers six lecture documents and two exercise documents (231 pages) with 45 candidate concepts. It is an example of a candidate coverage map awaiting review, not a bundled demo course: 41 pages have candidate mappings, 190 explicitly need review, and verification remains pending.

## Install the skill outside this repository

Codex discovers the repository skill when you open this clone. For use from other folders, install the entire [skill directory](.agents/skills/guided-learning/) in `~/.agents/skills/guided-learning/`, or ask `$skill-installer` to install that directory from this repository. Install the app separately. The skill's [app setup and launch reference](.agents/skills/guided-learning/references/learning-app.md) tells Codex how to find the runtime and open a prepared course.

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

The project uses GitHub Issues; engineering instructions start at [AGENTS.md](AGENTS.md). Project code is licensed under [MIT](LICENSE); bundled dependencies retain the licenses in [third-party notices](THIRD_PARTY_LICENSES.md).
