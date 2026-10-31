# Getting in, finding the way back, and where things live

Studio (ADR 0015 in PR #111) moves course work into the app. That changes the first hour of using Throughline, and it adds a fifth kind of thing to an interface that had grown one feature at a time:

- **Installing ended in Codex.** The learner pasted `Install …` into a Codex chat, setup printed a long welcome guide there, and the guide sent them to build a first course with `$throughline` in that same chat. With Studio, the first course is built in the app, so the guide points the wrong way, and it already described review at growing intervals after ADR 0014 removed them.
- **The way back was hard to find.** Setup adds a launcher (a Start menu entry on Windows, `~/Applications/Throughline.app` on macOS, a `.desktop` entry on Linux), but only one line of the welcome guide says so, in a chat the learner will not scroll back to. The command is `guided-learning`, which nobody remembers for an app called Throughline. The app never says how to open it next time.
- **The app explained nothing itself.** Selecting a passage to ask about it, clicking a citation, how help on an exercise is recorded and what Memory is were learned by stumbling on them or from the README.
- **The top bar put unlike things side by side.** Courses, Review, then Questions, Source, Notes and Memory as equal side panel views, with Studio about to join them. Questions, Source and Notes are used while reading a section; Memory and Studio are about the course as a whole and are used now and then.

## Installing

The Codex prompt stays the main way to install, since every learner already has Codex. Beside it:

- **An install script**, `install.sh` and `install.ps1` in the repository, run with one line (`curl … | sh`, `irm … | iex`). It installs uv when it is missing (uv brings its own Python, so Python stops being a prerequisite), removes the pre-0.5.1 package name, installs the package from `main` and runs `guided-learning setup`. It runs the same steps as the one-click updater (ADR 0015), so the two are kept together. It checks that `codex` is on PATH and says how to get Codex if not; it does not install Codex.
- **Setup opens the app** on the library when it finishes (`--no-open` to skip; the updater passes it, since it restarts the host itself). The welcome guide shrinks to the installed version, the library folder, where the launcher is, and "Throughline is open in your browser: make your first course in Studio". What studying looks like is explained in the app, where it can stay current.
- **A `throughline` command**, the same as `guided-learning`, which stays for scripts and the skill.
- **On macOS the launcher goes to `/Applications`** when it is writable, and to `~/Applications` otherwise.

A native installer (`.exe`, `.dmg`) is not built: see below.

## Finding the way back

The library shows a card, **Opening Throughline next time**, until the learner dismisses it: where the launcher is on this computer, in the words of that platform, with two actions the host carries out:

- **Add to desktop** copies the launcher there.
- **Show launcher** reveals it in Finder or Explorer, where the learner can pin it to the Dock or taskbar. Pinning cannot be done reliably by a program, so the app does not try.

The same text stays in Settings → About after the card is dismissed. Nothing starts at login (ADR 0004).

## Checking that Codex can run Throughline

When the library opens, the host checks what the app depends on: `codex` is found, the learner is signed in, and Codex has the App Server methods Studio needs (ADR 0015). While everything passes nothing is shown. A failing check appears on the library, above Studio, with what to do about it ("Sign in to Codex: run `codex login`", "Update Codex to use Studio"). Until then the hand-offs fall back to a Codex chat as ADR 0015 describes. These failures used to surface only later, as an error in a lesson.

## Three levels

Everything in the app belongs to one of three levels, and each level has its place on screen:

| Level | What belongs there | Where |
|---|---|---|
| **App** | The course library and making a new course; app-wide settings | The library page; Settings |
| **Course** | The route and chapters; review; changing the course; what the teacher remembers; the course's own settings | The route rail; chapter pages; the review page; the **Course page** |
| **Section** | The lesson and practice, and what is used while reading them | The reading column; the side panel |

**The side panel holds only what is used while reading a section**, in this order: **Questions** (used most, and it carries the count of open questions), **Source** (opened by citations), **Notes** (the learner's own). Memory leaves the side panel.

**The Course page** is the course-level place. The course title in the top bar opens it in the reading column, like a chapter page. It holds, in this order:

1. **Studio**, with this course's threads (below).
2. **Memory**, as the side panel showed it. The **Remember …?** banner still appears in the lesson where a preference comes up, and `m` opens the Course page at Memory.
3. **Sources**: the course's documents with their coverage and how many locations are not checked yet, with **Add files** and **Check sources**, which open Studio.
4. **This course's settings**, which move here from Settings → Course: teaching language, teaching preferences and exporting notes. The learner profile joins them when it can be shown and corrected (#73).

**Settings** keeps only what applies to every course: Teacher, Appearance and About.

## Studio's level

Studio is course-level. Each Studio thread belongs to one course and changes that course, and there is no course work that spans courses, so Studio lives on the Course page rather than as an app-wide place. The library holds only the case before a course exists: **New course** starts a Studio thread there, which becomes the new course's first thread once the skill creates it.

- **Studio is reached from where the need arises.** Add files, Check this location, a failed chapter build and the teacher's "change this in Studio" open the Course page's Studio with the request filled in and a chip saying where it came from (*Chapter 3*, *Section 3.2*, *notes.pdf p. 41*), sent with the message as context.
- **Studio work runs while the learner studies.** A Studio turn can run for minutes and stop to ask. While a turn runs, the top bar shows **Studio working…** on every page; when Codex asks for an approval or an answer it shows **Studio needs you**. The question itself waits in the Studio transcript, not in a popup, and one click opens it. So the learner can go back to the lesson, and Studio never has to sit beside it.
- **What the learner asks for in Studio reaches the teacher.** Studio may change how a course is taught. When the learner states a lasting requirement there ("always start from a worked example", "more rigour from chapter 3 on"), the skill records it as a confirmed preference in course memory (`memory.save` and `memory.confirm`), as it already does for preferences stated while a course is built, so the teacher follows it in every lesson and the learner sees it in Memory.

This replaces ADR 0015's "In an open course" placement, which made Studio a side panel view beside Questions, Source, Notes and Memory.

## Guidance in the app

Guidance comes in two parts.

**First, every place explains itself when it is empty**, and Help gathers the rest:

- The library's Studio gives examples of course work ("Make a course from these files", "Add this problem set", "Make chapter 3 more rigorous"), as ADR 0015 says, and says what to bring.
- Questions, Notes, Memory and the Course page's Sources say what they are for and how something gets there.
- **Help** (`?`) becomes a short map of what the learner can do, by level, with the keyboard shortcuts below it.

**Second, a few one-time hints** for the gestures nothing on screen reveals:

- selecting a passage to ask about it, highlight it or add a note;
- clicking a citation to open the page;
- that a hint or a solution is recorded, so a helped answer does not count as solved alone;
- what Memory is, the first time a **Remember …?** banner appears.

A hint appears next to what it explains, the first time that thing appears, one at a time, and is gone for good once dismissed or acted on. Which hints were seen is saved per user beside the settings, so it holds across browsers and courses. Anything visible on screen explains itself instead and gets no hint, which keeps the hints few enough to stay correct as features change.

## Considered and not chosen

- **A native installer** (`.exe`, `.dmg`). It needs signing and notarisation for every release and is a step towards the desktop app ADR 0004 rejected, while Codex is still required. The install script removes the Python prerequisite, which was the real gap.
- **Making the page an installable web app.** It would give a real Dock or taskbar icon, but when the host is not running the icon opens an error page; the launcher starts the host first.
- **Studio as a side panel view** (ADR 0015 as first written). It made Studio a peer of Questions, inviting content questions to go there and course changes to go to Questions, and it put a long-running, course-wide conversation in a panel meant for the section being read.
- **A Study / Studio mode switch.** It separates the two cleanly, but course work is occasional and almost always starts from something in a section; a mode would be one more state to be in.
- **Keeping flat tabs and only reordering them.** The order would improve; the mixed levels would remain.
- **An app-wide Studio** with threads filed by course. It would suit work across courses, which learners do not do.
- **A guided tour.** It explains everything at once, before any of it matters, and goes stale with every feature.
- **Starting at login**, to remove the need for a launcher. ADR 0004 keeps the app from running unasked.
