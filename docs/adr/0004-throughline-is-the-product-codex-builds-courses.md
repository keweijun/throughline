# Throughline is the study app; Codex builds the courses

The project began as a Codex skill with a local web view attached. It is now a study app, Throughline, for one self-directed learner who already uses Codex. Its job is to help them learn a subject properly from their own documents, across sessions, without losing their place. The route and lessons lead; the source reader and side questions support them. It is not a course-building interface, a tool for teachers or groups, a multi-provider AI app, or a desktop app.

Codex has two roles, split so the learner moves between the two tools in one step:

- **Teacher, inside the app.** Every lesson, side question, exercise and preparation runs through `codex app-server` in the background (ADR 0002). Studying never requires opening Codex.
- **Course builder, in Codex itself.** Creating a course, adding files, rebuilding a route and reviewing pages happen in a Codex chat. Codex already handles attaching files and images, reading them and asking follow-up questions; rebuilding that intake in the app would duplicate it and be worse. The app could run building turns over the same app-server connection, but deliberately does not.

## How the two connect

- **One Throughline folder** is both the course library and a dedicated Codex project: `~/Throughline` on macOS and Linux, `Documents\Throughline` on Windows, or `GUIDED_LEARNING_HOME`. Each course is a course workspace inside it (ADR 0001). `guided-learning setup` writes an `AGENTS.md` there saying it is a Throughline library and that course work goes through the `$guided-learning` skill, so any chat in the project behaves correctly. Setup registers the folder as a "Throughline" project through app-server (`project/create`), moves the install chat into it (`thread/metadata/update`, using the `CODEX_THREAD_ID` Codex gives its commands), and prints a welcome guide in English or Simplified Chinese (where the folder and launcher are, how to create a first course) for Codex to show in that chat. Outside Codex it prints a `codex://new` project link instead.
- **App to Codex.** The library page lists and opens courses but never edits them. Its "New course", "Add files" and "Review pages" actions open a new Codex chat in the Throughline project with the prompt filled in and the course named (`codex://new?prompt=…&path=…`), so the learner attaches files and sends. Where the link is not handled (CLI-only users, some Windows installs) the action copies the prompt.
- **Codex to app.** The skill ends course work by opening that course with `guided-learning open <course>`. An open Throughline tab notices changes to the course files and updates by itself.
- **Starting the app.** `guided-learning setup` adds a launcher (Start menu or desktop, `~/Applications`, or a `.desktop` entry) that starts the host if needed and opens the browser. Nothing starts at login.
- **One host** serves the library and owns one open course at a time; switching closes the previous `Host` and releases its lease.

Teaching in Codex's chat still works through the skill and shares the same course state, but it is a fallback: the README and the library send learners to the app.

## Distribution

Throughline is a Python package that bundles the skill (`guided_learning/skill/`); `guided-learning setup` installs it to `~/.agents/skills/guided-learning`, so the skill always matches the code it calls. The learner installs by pasting one prompt into Codex. The command, package and skill keep the names `guided-learning` and `codex-guided-learning`.

## Considered and not chosen

- **Building courses in the app.** Not because orchestrating Codex is hard (the app-server connection exists), but because it means building file and image intake, progress and resume that Codex already does well.
- **A standalone desktop app.** Every learner already needs Codex, so an installer, auto-update and signing add cost without removing a dependency.
- **A Codex plugin as the package format.** A plugin can bundle the skill but not the Python app. It can wrap the package later.
- **Skill only.** The course store, operation CLI and host are code that must be installed and versioned.
- **Other model providers.** Depending on Codex is part of the pitch ("uses the Codex you already have"), not a limitation to engineer away.
