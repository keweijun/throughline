# Getting in, finding the way back, and where things live

Studio (ADR 0016) moves course work into the app. That changes the first hour of using Throughline, and it adds a fifth kind of thing to an interface that had grown one feature at a time:

- **Installing ended in Codex.** The learner pasted `Install …` into a Codex chat, setup printed a long welcome guide there, and the guide sent them to build a first course with `$throughline` in that same chat. With Studio, the first course is built in the app, so the guide points the wrong way, and it already described review at growing intervals after ADR 0014 removed them.
- **The way back was hard to find.** Setup adds a launcher (a Start menu entry on Windows, `~/Applications/Throughline.app` on macOS, a `.desktop` entry on Linux), but only one line of the welcome guide says so, in a chat the learner will not scroll back to. The command is `guided-learning`, which nobody remembers for an app called Throughline. The app never says how to open it next time.
- **The app explained nothing itself.** Selecting a passage to ask about it, clicking a citation, how help on an exercise is recorded and what Memory is were learned by stumbling on them or from the README.
- **The top bar put unlike things side by side.** Courses, Review, then Questions, Source, Notes and Memory as equal side panel views, with Studio about to join them. Questions, Source and Notes are used while reading a section; Memory and Studio are about the course as a whole and are used now and then.

## Installing

The Codex prompt stays the main way to install, since every learner already has Codex. Beside it:

- **An install script**, `install.sh` and `install.ps1` in the repository, run with one line (`curl … | sh`, `irm … | iex`). It installs uv when it is missing (uv brings its own Python, so Python stops being a prerequisite), removes the pre-0.5.1 package name, installs the package from `main` and runs `guided-learning setup`. It runs the same steps the README gives Codex, which the one-click update also follows (ADR 0016), so they are kept together. It checks that `codex` is on PATH and says how to get Codex if not; it does not install Codex.
- **Setup opens the app** on the library when it finishes (`--no-open` to skip; the one-click update passes it, since Codex then restarts the host on the port the open tab uses), in the language setup was run in (`--language`, which the Codex prompt passes when the learner writes in Chinese). The welcome guide shrinks to the installed version, the library folder, where the launcher is, and "Throughline is open in your browser: make your first course in Studio". What studying looks like is explained in the app, where it can stay current.
- **A `throughline` command**, the same as `guided-learning`, which stays for scripts and the skill.
- **On macOS the launcher goes to `/Applications`** when it is writable, and to `~/Applications` otherwise.

A native installer (`.exe`, `.dmg`) is not built: see below.

## The first open

The first time the library opens after installing, with no course in it yet, a short series shows once, centred over the page, one step at a time:

1. **Language.** English or Simplified Chinese, already set to the language setup was run in, with the question in both languages. It changes the interface at once; Studio sets a new course's teaching language from the learner's own words, as before.
2. **How Throughline works.** The big picture in three stages: make a course (bring your files, say what you want to learn; Codex reads every page, asks about your goal and builds the route), learn (lessons in steps, citing their pages; ask about any passage on the side; exercises checked by part), review (whenever you ask: questions from memory, a drill, a mock exam).
3. **Codex works on your course.** What sets Throughline apart, and what learners otherwise never find out (ADR 0026): the teacher in Learn and Review is quick, Studio is Codex itself and can change the course whenever asked. Studio's writing box fills with one example request after another, then the access Studio runs with, since this is when the learner has just seen what it does. **Full access is the default**: reaching the step sets it, shown chosen and marked recommended, and the learner can pick Library access there or change it later in Studio's writing box. Studio is most useful when it can simply start rather than ask first. A learner who skips before this step keeps Library access, and the first course's introduction still offers Full access.
4. **Opening Throughline next time** (below), when there is a launcher. It ends with **Make your first course**, which puts the caret in New course.

Every step but the last has Skip, and Escape closes the series; however it ends, it does not show by itself again. Help keeps **How Throughline works**, which shows steps 2 and 3 again. A learner who already has courses (an update, not an install) sees only step 4, as before.

The series is deliberately not a tour of the interface: no panels, gestures or shortcuts, which the places themselves and the one-time hints explain (below) and which change with every feature. It shows only the workflow and Studio, which change rarely.

## Finding the way back

**Opening Throughline next time** is the last step of the first-open series, and for a learner who already has courses a dialog of its own, until the learner dismisses it: where the launcher is on this computer, in the words of that platform, and the two places worth keeping it, side by side:

- **Desktop: Add to desktop** copies the launcher there.
- **Dock or taskbar.** On macOS, **Add to Dock** adds it to the Dock (a `persistent-apps` tile, then the Dock restarts to read it); on GNOME, **Add to dock** adds it to the favourite apps its dock shows. Windows lets no program pin itself to the taskbar or Start, so there the card shows the four clicks instead: Start, type "Throughline", right-click it, Pin to taskbar. On another Linux desktop it says to add it from the app menu.

A **Show launcher** button, which revealed the launcher in Finder or Explorer for the learner to pin it there, came first. Learners did not know what a launcher was or what to do once it was shown.

The same text stays in Settings → About after the card is dismissed. Nothing starts at login (ADR 0004).

## Checking that Codex can run Throughline

When the library opens, the host checks what the app depends on: `codex` is found, the learner is signed in, and Codex has the App Server methods Studio needs (ADR 0016). While everything passes nothing is shown. A failing check appears on the library, above Studio, with what to do about it ("Sign in to Codex: run `codex login`", "Update Codex to use Studio"). Until then the hand-offs fall back to a Codex chat as ADR 0016 describes. These failures used to surface only later, as an error in a lesson.

## Three levels

Everything in the app belongs to one of three levels, and each level has its place on screen:

| Level | What belongs there | Where |
|---|---|---|
| **App** | The course library and making a new course; app-wide settings | The library page; Settings |
| **Course** | The route and chapters; review; changing the course; what the teacher remembers; sharing the course and exporting its notes | The route rail; chapter pages; the review page; the **Studio place**; Settings → This course |
| **Section** | The lesson and practice, and what is used while reading them | The reading column; the side panel |

**The side panel holds only what is used while reading a section**, in this order: **Questions** (used most, and it carries the count of open questions), **Source** (opened by citations), **Notes** (the learner's own). Memory leaves the side panel.

The places choose what fills the reading column; the side panel accompanies it. It belongs with Learn and Review, where a missed review question is checked against its source or asked about. **In Studio only Source opens beside it**: Studio's replies cite and change the course's documents, and a cited page belongs beside the chat, as it belongs beside a lesson. There is one reader and one list of the course's documents (**All sources**), the same in every place. Questions and Notes (the switcher, `/` or `n`, or asking about a selection) are about what is being read, so in Studio they go back to Learn with that view of the panel open; arriving in Studio sets an open Questions or Notes aside, and Learn and Review bring it back as it was.

**The Studio place** is the course-level place, labelled **Studio**, the first of the course's three places. The route rail steps aside for it, since its strip of chapters shows the route. It has no tabs. Studio stands in a frame from just under the top bar to just above the window's foot, at most 46rem wide, since a chat needs height to read back its history, questions and work, not width. Beside it, a column, as Codex lists its threads beside a chat:

1. **The course**: its title and goal, a strip of its chapters, each as wide as its sections and filled as they are studied (each opens its chapter page), and which chapter the learner is in. A course of one chapter shows no chapter line, since the title already names it.
2. **Chats**: this course's Studio threads, most recent first.
3. **How you're taught**: the confirmed preferences in course memory. Each has a × to delete it, confirmed beside it, since the teacher does not add a deleted one back; changing one is asked of Studio, as adding one is. They are added where they come up: a preference the teacher suggests is asked inline, right after what suggested it, and a lasting requirement told to Studio is recorded by it. A Memory tab with its own writing box came first; it duplicated Studio (ADR 0010).

The column scrolls on its own, however many chats and preferences there are, so the page never scrolls. Where Studio and the column no longer fit side by side, such as with a document open beside Studio, the column folds away, as Codex hides its list of threads, and Studio's own chats menu comes back above the transcript. `d` opens Studio with the caret in its box. The learner profile joins the column when it can be shown and corrected (#73).

**The top bar says where the learner is**, from left to right:

- **A breadcrumb, All courses › the course.** The logo and "All courses" lead to the library; the course's name opens a menu of the library's other courses, so switching courses does not need the library.
- **The course's three places, Studio · Learn · Review**, as one switch with the current place filled. A course is made and changed, studied and reviewed, and these are where; the way back to studying is always the same control, so Studio needs no "Back to reading".
- The section's position (Section 28 of 70) beside it.
- On the right, what is used while reading a section (Questions, Source, Notes), then Settings and Help.

Review stays one of the three places rather than a part of Studio: it is studying, used often. A plain course button, and before it a course title that opened the page, were tried first; learners did not read a title as something to click, and "Courses" beside a course's name (课程 beside 物理化学) read as two names for the same thing.

**Settings** holds what applies to every course, Appearance, Teacher and About, and, while a course is open, **This course** before About: sharing the course as a package (ADR 0020) and exporting its notes. Both are done now and then, so they stay out of the working places; changing the course is Studio's. Language stays in Settings, under Appearance and shown first, even though a course keeps its own: it also sets the interface, and Settings is where learners look for it. Teaching preferences need no entry of their own, since they are course memory.

## Studio's level

Studio is course-level. Each Studio thread belongs to one course and changes that course, and there is no course work that spans courses, so Studio is a place of the course rather than of the app. The library holds only the case before a course exists: **New course** starts a Studio thread there, which becomes the new course's first thread once the skill creates it.

- **Studio is reached from where the need arises.** Add files, Check this location, a failed chapter build and the teacher's "change this in Studio" open the course's Studio with the request filled in and a chip saying where it came from (*Chapter 3*, *Section 3.2*, *notes.pdf p. 41*), sent with the message as context.
- **Studio work runs while the learner studies.** A Studio turn can run for minutes and stop to ask. While a turn runs, the top bar shows **Studio working…** on every page; when Codex asks for an approval or an answer it shows **Studio needs you**. The question itself waits in the Studio transcript, not in a popup, and one click opens it. So the learner can go back to the lesson, and Studio never has to sit beside it.
- **What the learner asks for in Studio reaches the teacher.** Studio may change how a course is taught. When the learner states a lasting requirement there ("always start from a worked example", "more rigour from chapter 3 on"), the skill records it as a confirmed preference in course memory (`memory.save` and `memory.confirm`), as it already does for preferences stated while a course is built, so the teacher follows it in every lesson and the learner sees it under How you're taught.

This replaces ADR 0016's "In an open course" placement, which made Studio a side panel view beside Questions, Source, Notes and Memory.

## Guidance in the app

Guidance comes in two parts.

**First, every place explains itself when it is empty**, and Help gathers the rest:

- The library's Studio gives examples of course work ("Make a course from these files", "Add this problem set", "Make chapter 3 more rigorous"), as ADR 0016 says, and says what to bring.
- Questions, Notes, How you're taught and All sources say what they are for and how something gets there.
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
- **Studio as a side panel view** (ADR 0016 as first written). It made Studio a peer of Questions, inviting content questions to go there and course changes to go to Questions, and it put a long-running, course-wide conversation in a panel meant for the section being read.
- **The header across the top of a wide page**, with horizontal tabs under it (as first written). Stretched to the page's width, the chapter strip became one long bar, Studio started a third of the way down the window, and the lists and forms stood at a reading width at the page's left with the rest of it empty.
- **A course page labelled Overview**, with a header, a chapter strip and four tabs (Studio, Sources, Your notes, Share), as first written. It held almost no overview, so the label hid Studio, the agent that is Throughline's edge (ADR 0026), behind a word nobody reads as "Codex works on your course". Its own Sources duplicated the side panel's All sources and turned the top bar's Source into "go to a tab"; Your notes and Share each took a tab for one button or one form; and Studio had to share the page's height with the header, which took measuring code and a header that scrolled away as the learner wrote.
- **A course dashboard** in its place: the chapters, progress, what comes next, review. The route rail, the chapter pages and Review already show each of these, so it would be a fourth copy of the route, and it would put Studio one step further away.
- **A wide Studio.** A chat reads at a reading width; what it needs is the window's height.
- **The side panel kept off Studio** (the Overview as first written). A source cited in a Studio reply then opened in a tab of its own away from the chat, and the course had two readers and two lists of its documents.
- **Memory as a side panel view** that the learner talks to while reading (#114 as first written). Telling the teacher how to teach is about the whole course, like Studio, and suggested preferences are already asked inline where they come up, so nothing about Memory needs the section beside it. Keeping it in the panel would also split the course-level things between two places again.
- **A Study / Studio mode switch.** It separates the two cleanly, but course work is occasional and almost always starts from something in a section; a mode would be one more state to be in.
- **Keeping flat tabs and only reordering them.** The order would improve; the mixed levels would remain.
- **An app-wide Studio** with threads filed by course. It would suit work across courses, which learners do not do.
- **A guided tour of the interface.** It explains everything at once, before any of it matters, and goes stale with every feature. Only the big picture is shown at first open (above): without it, learners took Throughline for a chat tutor and never found Studio.
- **Starting at login**, to remove the need for a launcher. ADR 0004 keeps the app from running unasked.
