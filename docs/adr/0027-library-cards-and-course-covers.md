# The library is one course to carry on with and a card for each of the others, each with a cover; a new course begins on a page of its own

The library listed every course as a card carrying all it knew: the folder name, counts of sources and sections, the date, the goal Codex wrote down, the current section, a chip for unchecked source pages, an Open button and a menu at whatever height the text left them, and a row of links below. Since teaching moved into the app (ADR 0004) and course work into Studio (ADR 0016, ADR 0026), most of that is noise. A learner comes to this page to get back into a course, and sometimes to start one.

## Decision

### The page

- **The course to carry on with leads the page**, across its width, with the page's one strong button, **Continue**. It is the course that is open, or else the one studied last. The other courses follow as cards, three to a row on a wide window.
- **A card is a cover, the title and one line.** The line is the section the learner is at. It gives way to what needs saying: **Studio needs your answer**, **Studio is working on it**, or **Route not built yet** with **Build the route**. The whole card opens the course.
- **Nothing else is on a card.** The folder name, the counts, the date and the goal are gone. **Add files** joins Rename, Archive and Delete in the card's ⋯ menu (ADR 0022), which shows when the card is pointed at or focused. Unchecked source pages are no longer flagged here: the course page shows them, with the way to check them.
- **What Studio is doing in a course shows on its card**, from what the host saw (`studio.activity`), so a learner who left a chat finds it again. A new course still being made is a dashed card that reopens its chat.
- **Archived courses, deleted courses and the library folder** share one quiet row below the cards.

### Where a course begins

New course, which is also the whole library before a first course exists, opened on a large empty frame with a small question in its middle and the writing box at the window's foot.

- **Before anything is said, the page is the question, the writing box and ways to begin**, gathered in the middle of the window: "What would you like to learn?", the box right under it, and four suggestions (**Prepare for an exam**, **Learn a subject**, **Practise problems**, **Read a paper**) that start the request and leave the caret after it. Each is something a learner wants to do, so they stand at one level; where the files come from is not among them, since files are dropped whatever the aim (`lib/starts.ts`, which the library's Studio also suggests from). They are small chips, as suggestions are elsewhere in Studio: on this page nothing but a course looks like a course's card. **Import a course** is a line below them.
- **A contour map lies behind it**, clear where the question and the box are and fading towards the window's edges. It is drawn as the covers are (`covers.backdrop`), so the first page a learner sees is in the hand of the library it will fill.
- **Files let go anywhere on the page go to the box**, since the page asks for them; a course package still starts an import.
- **The first message turns the page into the chat** (ADR 0016): the frame across the page, the box at its foot. Reopening a chat that has begun shows the chat.
- The page is the same while Codex is starting, so nothing moves when it is ready.

### The cover

A cover is **the subject's short name over a pattern of thin lines**: 物化 over nested ellipses, DS over a tree.

- **Codex chooses both** (`cover.save`, `guided_learning/covers.py`), when it builds a course, when it next works on a course that has none, and when the learner asks for another. It has read the materials, so it knows that physical chemistry is 物化 to a student and that a course called "Midterm review: chapters 1–5" is data structures.
- **The name** is what a student would call the subject to a classmate: the usual abbreviation, or the plain subject name without what this course adds. It is in the course's teaching language and short, since it is set large.
- **The pattern** is one of a small library (`covers.PATTERNS`): contours, waves, lattice, grid, orbits, field, branches, scatter and ruled. Each says what it looks like and which subjects it suits, which is what Codex reads to choose (`cover.list`).
- **The app draws the patterns** (`web/src/lib/covers.ts`), in the interface's own ink with a few strokes in marker yellow, varied by the course's folder name so two courses with one pattern differ. A cover is therefore two short strings, and every cover is in the same hand in both themes.
- **A course without a cover shows a pattern alone**, so the page is whole before Codex has chosen anything. An unknown pattern is drawn as contours, so removing one from the library never breaks a card.
- **The cover is decoration.** It is hidden from screen readers; the title under it names the course.

The cover is an additive course record (`course/cover`), absent until set, so courses need no migration (ADR 0007). It travels in a course package at every share level (ADR 0020), since it belongs to the course and not to the learner.

## Considered and rejected

- **No cover.** The page without covers is already tidy. But a library of look-alike cards is hard to scan, and a name set large is found faster than a title read.
- **The course's key line** (a formula or phrase Codex picks, typeset). It is tied to the course more closely than a subject name, and real Codex chose well. Set in a tinted band it looked like a sticker, with fractions cut by the highlight; set on the card's own paper it was fine for formulas and weak for subjects without one.
- **A line drawing by Codex.** Real Codex drew valid, sensible sketches every time, but without labels some were hard to read, and two runs drew different things for one course. The app drawing a pattern Codex names gives the same tie to the subject without that variance.
- **The first page of the course's main source.** Real first pages are slide handouts, exam papers and title slides carrying a lecturer's name: uneven, and not the learner's to show.
- **The title's first character**, or a pattern the app picks from keywords in the title. Neither knows the subject: "物理化学" is chemistry, and a first character says nothing.
- **Progress, counts and dates on the card.** The learner asked for less on this page; Learn and Review show progress where it is used.
- **A list of rows.** The rest of the app is cards.
- **For the page a course begins on: three steps of how Throughline works.** The first-run series has just shown them (ADR 0017); this page is for doing the first of them. **Ghost cards where courses will be** say less than suggestions that start a request, and **suggestions drawn as cards with a cover's pattern** read as courses that are not there.

## Consequences

- `cover.list` and `cover.save` join the operations the skill names, so they are kept through 1.x (`docs/stability.md`); `course.status` gains `cover` once one is set.
- The patterns' names are stored in courses. A pattern may be redrawn, and new ones added; one that is removed is drawn as contours from then on.
- `/api/library` gains `cover` and `studio` for each course, and the page asks again when Studio starts, stops, asks or is answered in any course.
- ADR 0016 and ADR 0022 said a card carries Add files, Check sources and a menu beside Open; they are amended by this record.
