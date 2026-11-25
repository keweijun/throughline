# The library is one course to carry on with and a card for each of the others, each with a cover; a new course begins on a page of its own

The library listed every course as a card carrying all it knew: the folder name, counts of sources and sections, the date, the goal Codex wrote down, the current section, a chip for unchecked source pages, an Open button and a menu at whatever height the text left them, and a row of links below. Since teaching moved into the app (ADR 0004) and course work into Studio (ADR 0016, ADR 0026), most of that is noise. A learner comes to this page to get back into a course, and sometimes to start one.

## Decision

### The page

- **The course to carry on with leads the page**, across its width, with the page's one strong button, **Continue**. It is the course that is open, or else the one studied last. The other courses follow as cards, three to a row on a wide window.
- **A card is a cover, the title and one line.** The line is the section the learner is at. It gives way to what needs saying: **Studio needs your answer**, **Studio is working on it**, or **Route not built yet** with **Build the route**. The whole card opens the course.
- **Nothing else is on a card.** The folder name, the counts, the date and the goal are gone. **Add files** joins Rename, Archive and Delete in the card's ⋯ menu (ADR 0022), which shows when the card is pointed at or focused. Unchecked source pages are no longer flagged here: the course page shows them, with the way to check them.
- **What Studio is doing in a course shows on its card**, from what the host saw (`studio.activity`), so a learner who left a chat finds it again. A new course still being made is a dashed card that reopens its chat.
- **Archived courses, deleted courses and the library folder** share one quiet row below the cards.

### An empty chat, and where a course begins

An empty Studio chat was a small question in the middle of a large empty frame, a long paragraph, suggestions that wrapped unevenly, and the writing box far below at the frame's foot. New course, which is also the whole library before a first course exists, was that frame across the page.

- **Before anything is said, Studio is the question, the writing box and suggestions**, gathered in the middle of its frame: the question, the box right under it, and suggestions under the box that start a request and leave the caret after it. This is Studio's own layout (`studio.starting`), so a course's Studio and New course look alike.
- **Suggestions are small chips with an icon**, not cards: on these pages nothing but a course looks like a course's card. New course suggests four things a learner wants to do (**Prepare for an exam**, **Learn a subject**, **Practise problems**, **Read a paper**), so they stand at one level; where the files come from is not among them, since files are dropped whatever the aim. A course's Studio suggests adding files and three kinds of course work drawn from its range (ADR 0026), two to a row (`lib/starts.ts`).
- **The first message, or a chat opened, turns it into the chat** (ADR 0016), and the box travels to the frame's foot rather than jumping there. Starting a new chat brings it back the same way.
- **Studio is first seen in the layout it will keep.** Whether a course has a chat to open is asked of the host before Codex has started (`chats` in `/api/studio/activity`); until it answers, a moment, Studio shows nothing. So the box never moves under a learner who did not move it.
- **A course's Studio has no sheet until its chat begins.** The white sheet a chat is read on is right for a full chat and a large empty box for an empty one. So the question and the box stand on the page, and the sheet rises behind them to the frame's top as the first message is sent, its foot where the box lands. A new chat folds it away again.
- **The course's column is one quiet list** (amending ADR 0017's layout, not its content): the course's cover as in the library, its title and goal, the chapter strip, then Chats and How you're taught under small labels. A course with no chat yet has no Chats section; preferences are lines with a × that shows when one is pointed at. The writing box no longer names the chat, which the list beside it marks; it still says where a request came from.
- **A course is named twice in its Studio, not three times.** The top bar gives its title and the cover its short name (or the title, until Codex names it), so the column no longer writes the title under the cover. The course's own actions (Share…, Rename) are on the cover's corner.
- **The course switcher is a plain list**: each course's title and where the learner is, the open course on a tinted row (a tick read as a checkbox; version 0.62.1); then **All courses** and **New course**. It carries no cover patterns.
- **Patterns are decoration and stay where a cover is.** A pattern tells a learner nothing, so it is drawn on a course's cover (its card, and the top of its Studio column) behind the page a course begins on, and behind the question on Review's home (ADR 0014), a course's own lines on the page where its review begins; nowhere as a small mark to tell courses apart by.
- **In the writing box, the model and effort stand beside Send and the access with the attachments, as in Codex**, and one button stands where Send does: **Stop** while Codex works and nothing is written, **Add** once something is.
- **New course lays a contour map behind it**, clear where the question and the box are and fading towards the window's edges, drawn as the covers are (`covers.backdrop`), and drops the frame and the page's heading. The first page a learner sees is in the hand of the library it will fill.
- **Files let go anywhere on the New course page go to the box**, since the page asks for them; a course package still starts an import. **Import a course** is a line under the suggestions.

### The cover

A cover is **the subject's short name over a pattern of thin lines**: 物化 over nested ellipses, DS over a tree.

- **Codex chooses both** (`cover.save`, `throughline/covers.py`), when it builds a course, when it next works on a course that has none, and when the learner asks for another. It has read the materials, so it knows that physical chemistry is 物化 to a student and that a course called "Midterm review: chapters 1–5" is data structures.
- **The name** is what a student would call the subject to a classmate: the usual abbreviation, or the plain subject name without what this course adds. It is in the course's teaching language and short, since it is set large.
- **The pattern** is one of a small library (`covers.PATTERNS`): contours, waves, lattice, grid, orbits, field, branches, scatter and ruled. Each says what it looks like and which subjects it suits, which is what Codex reads to choose (`cover.list`).
- **The app draws the patterns** (`web/src/lib/covers.ts`), in the interface's own ink with a few strokes in marker yellow, varied by the course's folder name so two courses with one pattern differ. A cover is therefore two short strings, and every cover is in the same hand in both themes.
- **A course without a cover shows its title over a pattern**, so the page is whole before Codex has chosen anything, and no card reads as an unfinished blank: a title as long as a name may be is set as one, a longer one on two smaller lines (version 0.62.1; a pattern alone, as first built, looked like a cover left empty). An unknown pattern is drawn as contours, so removing one from the library never breaks a card.
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
- ADR 0016 and ADR 0022 said a card carries Add files, Check sources and a menu beside Open; they are amended by this record. Share (ADR 0020) opens across the list under the row its card is in, since its choices need more room than a card has.
- `/api/studio/activity` gains `chats`, the number of chats a course has, which costs nothing to ask.
