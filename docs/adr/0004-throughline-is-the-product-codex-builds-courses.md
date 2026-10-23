# Throughline is the study app; Codex builds the courses

The project began as a Codex skill with a local web view attached. It is now a study app, Throughline, for one self-directed learner who already uses Codex. Its job is to help them learn a subject properly from their own documents, across sessions, without losing their place. The route and lessons lead; the source reader and side questions support them. It is not a course-building interface, a tool for teachers or groups, a multi-provider AI app, or a desktop app.

Codex has two roles, split so the learner moves between the two tools in one step:

- **Teacher, inside the app.** Every lesson, side question, exercise and preparation runs through `codex app-server` in the background (ADR 0002). Studying never requires opening Codex.
- **Course builder, in Codex itself.** Creating a course, adding files, rebuilding a route and reviewing pages happen in a Codex chat. Codex already handles attaching files and images, reading them and asking follow-up questions; rebuilding that intake in the app would duplicate it and be worse. The app could run building turns over the same app-server connection, but deliberately does not.

## How the two connect

- **One Throughline folder** is the course library: `~/Throughline` on every platform, or `GUIDED_LEARNING_HOME`. It is not in Documents, because OneDrive and iCloud often sync Documents and syncing a live SQLite course risks corruption and two-machine conflicts that the course lease cannot see; setup moves courses from earlier default locations into it. Each course is a course workspace inside it (ADR 0001).
- **`$throughline` is the way into Codex.** The skill is named `throughline`, and the learner starts any Codex chat with `$throughline` to create, change or open a course; the skill addresses courses by name, so the chat's folder does not matter. Setup prints a welcome guide in English or Simplified Chinese (what to type, where the folder and launcher are) for Codex to show in the install chat. An earlier version created a dedicated Codex project through app-server and moved the install chat into it; the Codex app did not list projects created outside its own window, so this was dropped.
- **App to Codex.** The library page lists and opens courses but never edits them. Its "New course", "Add files" and "Review pages" actions open a new Codex chat with a `$throughline` request filled in and the course named (`codex://new?prompt=…&path=<library>`), so the learner attaches files and sends. The same hand-offs appear where the need arises while studying: below the route of an open course, on a source location that has not been checked, and on a course without a route. Because the link is not handled everywhere (CLI-only users, some Windows installs), every hand-off also copies its prompt and says so.
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
