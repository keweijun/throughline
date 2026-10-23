<p align="center">
  <img src="docs/images/wordmark-light.svg#gh-light-mode-only" alt="Throughline" width="356">
  <img src="docs/images/wordmark-dark.svg#gh-dark-mode-only" alt="Throughline" width="356">
</p>

<p align="center"><b>One line of teaching through all your documents.</b><br>A local study app that turns your PDFs and notes into a guided course, taught by Codex.</p>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">简体中文</a></p>

![A lesson in Throughline: the course route on the left, the current section with its goal, next step and a streamed lesson with citations](docs/images/lesson-en.png)

Throughline organizes several PDFs and Markdown documents into one source-linked route, then teaches it in your browser: unit overviews, streaming lessons, questions about any passage, the original page beside the explanation, practice, and a saved place to resume.

The teacher makes instructional judgments from your materials. The program validates state and references; it never decides on its own that you have understood something. Everything runs on your computer, with your own Codex as the teacher.

## Install

You need Codex, signed in (the desktop app or the [CLI](https://learn.chatgpt.com/docs/codex/cli)), and Python 3.10 or newer. Then paste this into Codex:

```text
Install https://github.com/keweijun/throughline
```

Codex reads the steps below, installs the app (no Node.js needed), adds the `$throughline` skill, creates your Throughline folder and a **Throughline** launcher in your app menu, and shows a short welcome guide. To **update**, paste `Update https://github.com/keweijun/throughline`; your courses are kept.

### For Codex: installing or updating Throughline

When a user asks you to install or update Throughline, run these steps yourself, outside the sandbox (they need the network and write outside the workspace). The user should not have to type anything.

1. If `guided-learning --version` already works, run `guided-learning stop` first. On Windows a running Throughline locks its own files and the upgrade would fail.
2. Install the latest version from GitHub, using the first tool that is available:
   - `uv tool install --reinstall "codex-guided-learning[pdf] @ git+https://github.com/keweijun/throughline"`
   - `pipx install --force "codex-guided-learning[pdf] @ git+https://github.com/keweijun/throughline"`
   - `python -m pip install --user --upgrade "codex-guided-learning[pdf] @ git+https://github.com/keweijun/throughline"`

   If `guided-learning` is then not on PATH, run `uv tool update-shell` (or `pipx ensurepath`) and use the full path the installer printed for the next step.
3. Run `guided-learning setup`, adding `--language zh-CN` if the user writes to you in Chinese. It is safe to repeat: it updates the skill and launcher and never touches existing courses.
4. Show the user the welcome guide that setup prints, as written. After an update, just say which version is installed (`guided-learning --version`).

### Install or update by hand

With [uv](https://docs.astral.sh/uv/) (recommended):

```sh
guided-learning stop                 # when updating; skip on a first install
uv tool install --reinstall "codex-guided-learning[pdf] @ git+https://github.com/keweijun/throughline"
guided-learning setup                # add --language zh-CN for the Chinese welcome guide
```

With pipx, replace the second line with `pipx install --force "codex-guided-learning[pdf] @ git+https://github.com/keweijun/throughline"`. Both forms always fetch the latest version, so the same three lines install and update. Run `guided-learning --version` to see what you have.

To uninstall, run `guided-learning stop`, then `uv tool uninstall codex-guided-learning` (or `pipx uninstall codex-guided-learning`), and delete `~/.agents/skills/throughline` and the launcher. Your courses stay in your Throughline folder until you delete it.

## Create your first course

After installing, Codex shows a short welcome guide. From then on, start any Codex chat with **`$throughline`** to work on your courses.

1. Type `$throughline make a course from these files`, attach your PDFs or notes (or name the folder they are in), and say in a sentence what you want to learn, for example "quantum mechanics up to perturbation theory, for my exam".
2. Codex asks a few quick questions: your goal and deadline, how well you know each prerequisite it found in the files, and how much detail you want. Then it suggests a course name, copies your files into the Throughline folder, builds a route across them and tells you what still needs checking.
3. When it is done, the course opens in Throughline in your browser. Next time, open it from the **Throughline** launcher in your app menu.

Later courses work the same way: `$throughline` in any Codex chat, or **New course in Codex** in the Throughline library.

## How it works

Throughline is where you study; Codex is where courses are built. You move between them in one click.

- **Study in Throughline.** Open it from the **Throughline** launcher in your app menu (setup adds it). Lessons, questions and practice run Codex in the background, so you never need Codex open to study.
- **Build courses in Codex.** Start any Codex chat with `$throughline`. In the library, **New course in Codex**, **Add files in Codex** and **Review in Codex** open a new Codex chat with the `$throughline` request typed in: attach your files and send. Codex reads them, builds the route and opens the course in Throughline when it is done; an open Throughline tab updates by itself.
- **Ask for anything.** `$throughline add this problem set to quantum`, `$throughline make the quantum course more rigorous`, `$throughline open quantum`. Codex asks for permission the first time it starts Throughline, because the app keeps running in the background.

![The course library listing three courses with their sources, sections, review backlog and current section](docs/images/library-en.png)

## Study

- **Route and goal.** The left rail is the course route; each section shows its goal and the next thing to do.
- **Lessons.** The first lesson of a section opens with a unit overview, then teaches. Text streams in and is saved when complete; you can pause or ask for another pass.
- **Side questions.** Select a sentence or formula and ask about it. The lesson keeps going unless you pause it. Questions that a later section answers properly are saved for that section.
- **Sources.** Hover a citation to see the cited text; click it to open the exact page or line in the built-in reader. Unchecked sources stay marked "Pending verification".
- **Practice.** Exercises follow each lesson. Hints and solutions are always available, but help is recorded, so a helped answer is never counted as solved on your own.

<table>
  <tr>
    <td><img src="docs/images/reader-en.png" alt="The PDF reader open beside the lesson at the cited page"></td>
    <td><img src="docs/images/questions-en.png" alt="A side question about a highlighted passage, answered in the side panel"></td>
  </tr>
  <tr>
    <td align="center">The cited page, beside the lesson</td>
    <td align="center">A side question about a passage</td>
  </tr>
</table>

The interface and new teaching default to English; switch to Simplified Chinese under Language in Settings (the gear in the top bar). Imported materials and earlier records keep their original language. More in [using the interface](docs/learning-ui.md).

## Where things live

- **Courses:** your Throughline folder, `~/Throughline` (`C:\Users\<you>\Throughline` on Windows). It is deliberately outside Documents, which OneDrive and iCloud often sync: a course's database can be corrupted by sync. To use another folder, set `GUIDED_LEARNING_HOME`; if you point it at a synced folder, open each course on only one computer at a time. It holds an `AGENTS.md` that tells Codex how to work there. Each course is one subfolder holding its source files (`inputs/`), snapshots, route, position and learning evidence; to move a course, stop the app and copy its folder.
- **Teacher settings:** open **Settings** (the gear in the top bar) to pick the Codex model and reasoning effort. They are saved per user in `~/.config/guided-learning/settings.json` (`%APPDATA%\guided-learning\settings.json` on Windows), never in a course.

Extracted text does not verify formulas, images or coverage, so the library and reader show what still needs review. See [creating and reviewing a course](docs/course-import.md).

## Commands behind the prompts

```sh
guided-learning setup                 # install or update the Codex skill
guided-learning open [course] [--no-browser] [--port 8765]
guided-learning stop
guided-learning courses               # the library as JSON
echo '{"op":"course.status"}' | guided-learning --course quantum
```

The last form is the operation entry point the skill uses; it reads one JSON request from standard input or `--request file.json` and returns `{ok, result}` or `{ok:false, error}`. `--workspace <folder>` addresses a course outside the library, and `guided-learning-web --workspace <folder>` serves one in the foreground. The skill and its operation references are in [guided_learning/skill/](guided_learning/skill/SKILL.md).

## Development

```sh
python -m venv .venv
.venv/bin/python -m pip install -e ".[pdf]"        # Windows: .venv\Scripts\python.exe
.venv/bin/python -m unittest discover -s tests
.venv/bin/guided-learning setup                     # copy this checkout's skill to Codex; rerun after editing it

cd web && npm install
GL_HOST=http://127.0.0.1:8765 npm run dev          # hot-reloading UI against a running host
npm run check && npm run build                     # type check, then write guided_learning/web_dist (commit it)
npx playwright test                                # browser tests against disposable fixture courses
```

Read [architecture](docs/architecture.md), the [glossary](GLOSSARY.md) and the [decisions](docs/adr/) before larger changes; agent instructions are in [AGENTS.md](AGENTS.md). Tasks live in GitHub Issues.

Throughline is licensed under [MIT](LICENSE); bundled dependencies keep the licenses listed in [third-party notices](THIRD_PARTY_LICENSES.md). The Python package and command are named `guided-learning` (package `codex-guided-learning`).
