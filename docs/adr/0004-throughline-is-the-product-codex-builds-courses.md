# Throughline is the product; Codex builds the courses

The project began as a Codex skill with a local web view attached. It is now a study app, Throughline, where the learner spends their time: a course library, lessons, side questions, the source reader and practice. Codex has two roles in it. It is the only teacher (ADR 0002), and it builds and changes courses, because reading documents, drawing up a route and judging coverage need a model. The `$guided-learning` skill is how a learner asks Codex for that work and how Codex opens the app. It is no longer the product.

This shapes three things:

- **One course library per user.** Courses live as course workspaces in a per-user data directory (`GUIDED_LEARNING_HOME`, by default `~/.local/share/guided-learning`, or `%LOCALAPPDATA%\guided-learning` on Windows), not in a repository checkout. The host serves the whole library and owns one open course at a time. Switching courses closes the previous `Host` and releases its lease, so ADR 0001's single-owner rule holds per course.
- **The library page is read-only.** It lists courses and opens them. Creating a course, adding sources, rebuilding a route and reviewing coverage stay in Codex, and the page shows the prompts to paste. This keeps the app from growing a second course-building agent, upload handling or import jobs alongside Codex.
- **Distribution is a Python package with the skill inside.** `guided_learning/skill/` ships in the package, and `guided-learning setup` copies it to `~/.agents/skills/guided-learning`, so the skill always matches the code it calls. The learner installs by pasting one prompt into Codex. `guided-learning open` starts the host in the background and reuses it, so the learner never runs a command themselves.

Considered and not chosen:

- **Managing courses in the app.** Uploads plus a "build route" button would mean either a second model client or orchestrating Codex runs from the host, with progress, cancellation and resume to handle. That is a larger surface than the hand-off it removes. It is the next step if the hand-off proves to be the main friction, and it should be added as one Codex turn type in the existing turn engine (ADR 0003).
- **A standalone desktop app.** Every learner already needs Codex, so an installer, auto-update and code signing would add cost without removing a dependency.
- **A Codex plugin as the package format.** A plugin can bundle the skill but not the Python app, so it would not save the learner an install step. It can be added later as a wrapper.
- **Skill only.** A skill is instructions. The course store, the operation CLI and the host are code that has to be installed and versioned.

The command, package and skill keep the names `guided-learning` and `codex-guided-learning`, so installs and courses created before the rename keep working.
