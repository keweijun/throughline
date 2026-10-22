# Find and open the learning app

The app and this skill are separate installations. A course workspace contains `course.sqlite3`; registered source snapshots appear under `sources/`. A valid new course may not yet have a `sources/` folder. The workspace is not a copy of this skill. Do not assume that the maintainer's ignored `work/courses/quantum-v1` exists on someone else's computer.

## Find the app and course

1. Prefer a repository checkout that contains `pyproject.toml`, `guided_learning/`, and a project virtual environment. When this is a repository-scoped skill, search upward from the current working directory or skill path. For a personal skill copied elsewhere, look for an existing installed `guided_learning.web` using the chosen Python interpreter; ask the learner for a known checkout or course path only when it cannot be found.
2. Use the Python interpreter that installed the app. Check `python -m guided_learning.web --help` with it before launching. On Windows, the repository environment is usually `.venv\Scripts\python.exe`; on macOS/Linux, `.venv/bin/python`. A skill folder alone is not an executable app.
3. Confirm the requested course path by running `course.status` and `session.resume` through the same environment. `curriculum.view` must have a nonempty route to start lessons. Preserve the existing workspace and progress. If the course is missing, prepare one via [course operations](course-operations.md) and [curriculum operations](curriculum.md). Never substitute another course merely because it happens to exist locally.

If the app is absent and the learner asked you to set it up, install this repository's Python package into a fresh environment in a suitable checkout. Reuse an existing checkout when possible; otherwise clone `https://github.com/keweijun/codex-guided-learning.git` into a new directory. Install from that checkout with `python -m pip install -e '.[pdf]'` using its virtual environment. Keep personal source files and course state outside Git-tracked code. If the learner asked only for instructions, give the setup command instead of changing their machine.

## Start and verify the UI

1. Start `python -m guided_learning.web --workspace <absolute-course-directory>` using the app interpreter. Keep the host alive while the learner studies. Use an interactive terminal when available; on Windows, hide a noninteractive background process window. Do not wait indefinitely for a long-running host command to exit.
2. Use the URL printed at startup, normally `http://127.0.0.1:8765/`. If the port is occupied, read the existing host's `/api/state` and compare its course ID with `course.status`. Reuse only a matching host; otherwise choose another loopback port with `--port`. The host's course lease prevents two hosts from owning the same course.
3. Fetch `/api/state` and verify the requested course title and current position. Open the URL with an available browser or Codex UI tool. If a browser-opening tool is unavailable, give the learner a clickable URL. Tell them which course is open and whether source verification is still pending.

The app listens on loopback. If the Codex agent and the learner's browser are on different machines, a localhost URL on the agent's machine is not automatically reachable from the learner's computer. Explain that situation and use an approved connection method before saying the page is open. Do not expose the host to a public interface as a shortcut.

The Codex CLI supplies the teacher model. If model execution fails, keep the course and any partial response, report the actual error, and help the learner check their Codex setup. Do not claim that a page load proves a lesson can complete.
