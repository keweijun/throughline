# Studio: course work happens in the app

ADR 0004 split Codex's two roles between two tools: Codex taught inside Throughline, and courses were built in a Codex chat that the app opened with a `$throughline` request filled in. The reason was intake. Codex already attached files and images, read them, asked follow-up questions and showed its progress, and rebuilding that in the app looked like duplicated work that would come out worse.

In use, the split is the roughest part of the app. Every course starts in another tool, every new set of files sends the learner away and back, and the hand-off itself is fragile: the `codex://` link is not handled by the Codex CLI or by some Windows installs, so the learner gets a copied prompt to paste. Meanwhile most of what intake needs is already in the host: it drives `codex app-server` with saved threads (ADR 0002), sends images as `localImage` inputs, streams turn events over SSE and builds outlined chapters in the background. What was missing is a turn that may write and that runs for minutes while asking the learner questions, and the App Server supports that directly.

So course work moves into the app. **Studio** is where the learner creates and reshapes courses by talking to Codex: making a course from files, adding files, rebuilding or regrading the route, checking pages, changing how a course is taught. It is a Codex chat in all but window: the same model, the same `$throughline` skill and the same conversation, drawn by Throughline. A learner who prefers a Codex chat can still use `$throughline` there; Studio and the chat share the skill, so neither drifts from the other the way chat teaching once did.

## Name and place

Its label is **Studio**, with "Create and change courses with Codex" under it: the name is a place in the app, and the line says what runs it. The name says what Studio is for: big requests that change a course, not questions about its content, which stay in **Questions** with the teacher. Its empty state and composer placeholder give examples of course work ("Make a course from these files", "Add this problem set", "Make chapter 3 more rigorous") rather than an invitation to ask anything.

- **No course yet**: Studio fills the library page. It is the way into the app.
- **Library with courses**: Studio stays at the top of the library page, above the course list; **New course** starts a Studio thread, which becomes the new course's first thread.
- **In an open course**: Studio is the first part of the course's **Course page**, with the course's threads (amended by ADR 0017; it was first a side panel view next to Questions, Source, Notes and Memory). The hand-offs that used to open Codex (Add files and Check sources, checking an unchecked source location, building a route for a course without one, the fallback for a failed chapter build) open it with the request filled in and a chip saying where the request came from. While a turn runs, the top bar shows that Studio is working or needs the learner, so they can go on studying.

The teacher in lessons and Questions cannot change the course, but it can **suggest a course change**. When it judges that a change to the course itself would help the learner (a prerequisite the route lacks that they keep needing, a section they keep finding too fast, the learner asking Questions to change the course), its reply ends with a hidden `<course-change>` block holding the request. The learner sees "Change the course? …" under that reply, in the same place and style as a suggested preference (ADR 0010), with **Open in Studio**, which fills Studio with the request and a chip naming the section without sending it, and **Not now**. Either answer closes it. One is open at a time: a new suggestion supersedes any still open. The teacher decides when to suggest, with no fixed triggers or counts, and is shown its earlier suggestions and what became of them, so it does not repeat one. There are no standing "change this in Studio" buttons on the route, chapters or reader: suggestions appear only where the learner is already reading. The suggestions are an additive course record (`course_change`), read as empty when absent, so courses need no migration (ADR 0007).

## A native Codex chat

Studio should feel like Codex, because the learner already knows Codex. It covers every App Server feature that course work uses, and leaves out the ones that only serve coding.

**Composer.**

- `$` opens a skill picker from `skills/list`; the message carries `skill` inputs. `$throughline` is preselected and shown as a chip.
- `@` searches the course's files and sources (`fuzzyFileSearch`) and inserts `mention` inputs.
- Images pasted or dropped are saved and sent as `localImage`, as answer images are today.
- Files dropped or attached are copied into the course's intake folder (for a new course, a new folder in the library) and mentioned, so the skill registers them from inside the library.
- Skills and files render as chips in the text (`text_elements`), and still do when a thread is reopened.
- A message sent while Codex works steers the running turn (`turn/steer`); Stop interrupts it (`turn/interrupt`). The up arrow recalls the last prompt in an empty composer.
- `/` lists the commands that make sense here, plus the enabled skills: `/new`, `/model`, `/reasoning`, `/fast`, `/plan` (plan mode, `collaborationMode: plan`), `/compact`, `/status` (context and rate limits), `/rename` and `/archive`. Cloud, worktree, project, git review, IDE, MCP and other coding commands are left out: a command that does nothing here feels less native, not more.

**Live work.** The reply streams as Markdown through the lesson renderer. Reasoning summaries are folded. A command shows Codex's parsed actions ("Read chapter2.pdf", "Searched for …") with its output folded; file changes show their diff; Codex's plan is a live checklist; web searches, MCP tool calls, viewed images, compaction markers, warnings and errors appear inline. A small meter shows context use and rate limits.

**Codex asks.** Approval requests (commands, file changes, extra permissions) and Codex's questions to the learner (`item/tool/requestUserInput`, with options and an Other answer) appear in the transcript; Enter approves and Esc declines, as in Codex. The skill asks its intake questions this way: goal and deadline, prior knowledge, depth.

**Threads.** Each course has its own list of Studio threads, most recent first, which can be resumed, renamed, archived and started anew. Studio threads are saved Codex threads in the library folder, so the same conversation may also appear in the Codex app. Which threads belong to which course is kept per user beside the settings (`~/.config/guided-learning/`), not in the course workspace, because the threads live in the learner's Codex home and do not travel with a course. Studio threads carry their own `serviceName`, apart from the teaching threads the host deletes when idle (ADR 0002), so cleanup never removes them.

Left out: realtime voice, the terminal, `fs/*`, git, review mode, plugin and MCP management, external agent import and sub-agents. They belong to Codex's own app.

## Access

Studio turns run in the library folder with Codex's workspace-write sandbox, the library as the writable root, and approval only on request. Codex reads anywhere, so files outside the library (the learner's own folders of PDFs) need no approval, and it writes courses and runs `guided-learning` without asking; it asks only to write outside the library or reach the network.

**Full access**, a switch in Settings → Teacher, runs Studio turns with no sandbox and no approvals, as many learners run Codex itself. On Windows, where Codex's sandbox needs setting up, the host checks `windowsSandbox/readiness`: if the sandbox is not ready, Studio starts with Full access and says so in Settings, matching how Codex runs there.

Teaching turns are unchanged: read-only, and the host saves what they return (ADR 0002, 0004).

## The skill in Studio

Building logic stays in the skill, so Studio and a Codex chat build courses the same way. Studio adds developer instructions to its threads saying that the learner is in Throughline Studio, which course is open, and that the app is already open: the skill skips `guided-learning open` and ends by naming the course, and the app opens or refreshes it (an open tab already notices course changes). The skill's operations keep their names and semantics.

## Updating in one click

ADR 0004 left updating to Codex because a deterministic updater would run from the installation it replaces, and on Windows a running Throughline locks its own files. A detached helper avoids both:

1. **Settings → About → Update now** appears when `main` is newer (ADR 0004) and the host can tell how it was installed: a `uv tool`, `pipx` or `pip --user` installation. For an editable or unknown installation it shows the commands instead.
2. The host writes a small updater script to a temporary folder and starts it as a detached process with the installer's own Python, outside the environment being replaced, passing the host's process ID, port and open course. It refuses while a Studio turn is running, and pauses teaching turns as on close.
3. The host shuts down. The updater waits for it to exit, removes the pre-0.5.1 package name, runs the README's install command for that installer, runs `guided-learning setup` (its welcome guide goes only to the log), and starts the host again on the same port with the same course, writing its steps to `~/.config/guided-learning/update.log`.
4. The open tab shows that Throughline is updating, reconnects when the host is back, and reloads once `/api` reports the new version. If the host does not return, the tab, which still runs from the old page, shows the log's last lines and the `Update https://github.com/keweijun/throughline` request to paste into Codex, the hand-off used until now.

The first install still starts in Codex, since there is no app yet.

## Fallback and versions

Studio uses experimental App Server methods. The interface types the fields it reads after the protocol of the Codex version it is tested against (`codex app-server generate-ts`), and the host checks at start-up that the methods Studio needs exist. When they do not, the hand-offs keep opening a Codex chat as before (ADR 0004), and the Studio panel says that a newer Codex enables it.

## Considered and not chosen

- **Embedding an existing Codex web UI.** The open-source ones are general coding workbenches (projects, git, terminals), in React or Next.js with their own servers, and the closest match has no license. Hiding most of a fork and keeping it current costs more than one panel, and it would not look like the rest of Throughline. Their composer behaviour is worth studying; MIT-licensed parts (CodexMonitor) can be ported with attribution.
- **A bundled harness instead of Codex.** It would bring back provider and key handling (ADR 0002), put a second runtime into the package and give up "uses the Codex you already have".
- **Keeping course building in Codex.** Kept only as the fallback above.
