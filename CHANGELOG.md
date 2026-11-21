# Changelog

What changed for learners in each release of Throughline, newest first. Each release is tagged `v<version>` on GitHub, and the `stable` branch points at the latest one. Every pull request that bumps the version adds its entry here (AGENTS.md, Versions); CI publishes the entry as the release's notes.

## 0.61.0

- **Hand things to Studio without leaving what you're doing.** When a drill can't do what you ask, such as a cheat sheet or collecting a problem set, the teacher offers it to Studio right under its reply. One click sends it, with what you were reviewing, and the card shows Studio working, then **Done** with **Open**. A suggested course change now works the same way, as does **One-page summary in Studio** beside a chapter's key points.
- **More ways to review.** Next to Drill me: **Explain it back**, **Oral quiz** and **Tell confusable ideas apart**. With Studio: a **Mock exam**, a **Formula sheet** and **My mistakes on one page** for what you chose to review.
- **Meet Studio.** The first course you open now says what Studio is, with three things it could do for that course, each one click away. With full access Studio starts straight away; without it, Throughline asks once before each request.
- **Tidier cards.** Several cards are now balanced, with what they say on the left and the action on the right:
  - **Next step** under a lesson, with Continue at its bottom right;
  - the warm-up, now with a close button;
  - skipping a chapter, and the chapter drill.

  **Back to current section** sits beside the chapter's name, and an exercise's **Another like this / Do later / Skip** stay on the right when they wrap.

## 0.60.0

- **Drill sessions replace review sets.** In Review, **Drill me** starts a quick back-and-forth with a fast teacher on what you chose to review. It asks a few questions at a time, mostly on what you missed before and what you haven't practised for a while, and you answer them right there. Ask for **More questions**, ask about an answer, or say what to drill next. Nothing to finish and nothing due: a session is kept under **Earlier sessions**, and you can pick it up again whenever you like. Your answers count just as before, and misses go into your mistakes book.
- **Drill this chapter** on the chapter page replaces the chapter quiz. It starts with one or two exercises from the chapter you've done before, then asks new ones. Your earlier quizzes stay on the chapter page.
- **The warm-up** before a section is now a short drill on what the section builds on, right on the section page.
- **Test me on this** under a key point, and **Try it again** under a mistake, start a drill on just that.
- Review sets you already have stay in Review, under **Review sets from before**. Codex in Studio no longer writes review sets: when you ask it to help you review, it points you to Review.

## 0.59.0

- **The Review page is now a place with several ways to review.** It opens on your key points, and the mistakes book is one tab away. Questions sit beside them on a wide window.
- **Choose what to review**: everything you have studied, or only some chapters or sections. The key points, the mistakes and the questions you ask for all follow your choice, and Throughline remembers it for the course.
- **Test me on this** under a key point, and **Try it again** under a mistake, ask the teacher for questions on just that.

## 0.58.0

- **A mistakes book on the Review page.** It collects what you missed: exercise parts, chapter quiz and review questions, and ideas whose check questions you got wrong more than once. Each entry shows what you answered and the feedback, and links back to the question or lesson step. When you later get one right, it stays, marked with the date, under **Since got right**.

## 0.57.0

- **Key points.** Every section you study now ends with its key points: the results, rules and methods to hold from it. Each one says when it holds and gives a common mistake, often one you made, and links back to the lesson step and the page that taught it. They show at the end of the lesson and at the top of the section when you come back to it. Sections you studied before this update get their key points in the background while Throughline is idle.
- **A chapter's key points on one sheet.** The chapter page gathers the key points of the sections you studied, opened by a short paragraph on how they connect. This replaces the chapter recap, which almost no one used. Recaps you already have stay on the chapter page, folded.
- **To change a key point, ask Codex**, from **Ask Codex to change them** beside the points ("say it without the matrix notation", "add the sign convention"). When the section is taught again, its new key points keep the changes you asked for.

## 0.56.0

- **The Overview on a wide window** puts the course's title, progress and tabs in a column on the left. Studio and an open document start at the top of the page and reach the bottom of the window, and Sources, Your notes and Share sit beside the column instead of at the far left of an empty page. On a narrower window the header stays above the tabs, as before.
- **New course** gives Studio the page: it is wider, the chat sits in one centred column as on the Overview, and the box reaches the bottom of the window.
- **A long list of how you're taught** scrolls beside Studio rather than running past the bottom of the window, and its entries take less room.
- **Going back to Learn from the Overview** returns you to where you were reading. Before, after opening a document on the Sources tab, Learn could come back scrolled to another place in the lesson.

## 0.55.4

- If you updated while an older Throughline (0.54.0 or earlier) was still running, the launcher and `guided-learning open` now stop it and start the new version, and `guided-learning stop` stops it. Before, the browser opened on the old version without signing in, and the old one could not be stopped.
- On Windows, the host key and the host's output log are now readable by your account alone, as they already were on macOS and Linux. Before, they took the permissions of your Throughline folder.
- After a document of a course is updated, Codex can save a chapter again with its links moved to the new version of the document. Before, that save was refused.
- "Back to the passage" on a side question now unfolds an earlier lesson that a new lesson replaced, and shows the passage in it.

## 0.55.3

- Stop in Studio no longer leaves Studio busy when Codex agrees to stop but keeps working. If the turn has not ended a few seconds after Stop, Throughline restarts Codex, so you can update Throughline, delete a course and start a new chat again. Your chats are kept.
- Throughline now finds a Codex you installed with npm when it is opened from Finder, Spotlight or an app menu even if `node` lives in a different folder from `codex` (as with nvm, Homebrew or Volta). Run setup again (or update) to pick this up.
- After you run setup again and it finds Codex somewhere new, an open Throughline uses the new Codex right away instead of the old one until it is restarted.

## 0.55.2

- A course whose deletion was cut short, because Throughline was closed or the computer shut down at that moment, works again the next time you open it or change it. Before, it stayed in the library but refused every change, telling you to restore it from a trash that did not hold it.
- Setup moving your courses from where an earlier version kept them now waits for anything Codex is saving in a course to finish, so nothing is left behind in the old folder. On Windows a course that is still open somewhere stays where it is, whole, instead of being half copied. And a course archived in one old location no longer archives a different course of the same name.
- A copy of a course folder you made yourself is now its own course to Throughline: a tab still showing the original reloads instead of saving your notes into the copy or downloading the copy when you export.

## 0.55.1

- A course with a very long text source, such as a full transcript, can now be imported from its package. Before, the import could refuse a package Throughline had just exported, so a backup of such a course could not be restored.
- Exporting a course whose saved copy of a source is damaged now says so and asks you to register that source again, instead of making a package that would not import.
- Exporting the same course twice at once to the same file, say once to share and once as a backup, no longer mixes the two: a Route package can no longer pick up your notes or progress from the other export.
- Importing a Route and lessons package made by Throughline 0.54.0 or earlier no longer carries the sender's own wording of their lesson requests, or the teacher's notes about them, into your course.
- A whole-course package now holds only the images attached to your answers, questions and notes, not every image the course folder kept.

## 0.55.0

- A section you have studied can be taught again as a **new lesson**. Below the lesson, choose New lesson instead of Another pass: the teacher plans the section afresh in steps, from what it covers now, and knows what your earlier lesson taught. Ask for only what the last lesson skipped, more rigour or the proofs, or leave it empty for the whole section. The earlier lesson stays folded above the new one, with your answers and notes, and the section stays studied.
- A lesson you have not finished can be started over the same way, with "Start a new lesson instead" below it. You no longer have to finish a lesson you have moved past.
- When Codex fixes a section you have already studied, it now asks you to take a new lesson on it, instead of adding extra sections to get the new material taught.
- A shared course carries only each section's current lesson, not the ones a new lesson replaced.

## 0.54.6

- On a Mac, opening Throughline from Finder, Spotlight or the Dock now finds a Codex you installed only for the terminal (the `codex` command), so lessons and Studio work there too. Before, Throughline could say Codex was not found unless the Codex app was installed. This also applies to app-menu launchers on Linux. Run setup again (or update) to pick up where your Codex is.

## 0.54.5

- Running two versions of Throughline side by side, or a command while Throughline is open, no longer loses settings, Studio chats or archived courses. Before, when both saved at the same moment, one could overwrite what the other had just saved: a chat could drop out of a course's Studio list, or a course you archived could show up again.

## 0.54.4

- If Codex stops responding in Studio, Stop now works: Throughline restarts Codex and says so, instead of leaving the chat working until you quit. Before, a stuck Codex also kept you from updating Throughline or deleting a course. Your chats are kept; send a message to carry on.

## 0.54.3

- After you update a document that one chapter uses, Codex can still build or fix the other chapters. Before, saving any chapter failed until every mapping to the old version of that document had been redone.

## 0.54.2

- A page left open on one course no longer writes into another. If you opened a different course since, in another tab say, a note, answer or other change sent from the old page is no longer saved into the course that is open now: the page reloads into the course that is open instead. The same goes for downloading a course package from Share, which could hand out the other course's file.

## 0.54.1

- Sharing a course at Route and lessons no longer passes on what you asked your teacher in your own words, or what the teacher noted about you. The person you share it with sees the lessons as if they had pressed Start lesson and Continue themselves.
- A course someone shared with you keeps its lessons when you share it on.
- A backup made while Codex was adding a document now always holds that document's saved copy. Throughline refuses to export a course that is missing one, and to import a package that is, instead of making a course with a gap you would find only later.
- Deleting a course while Codex is saving something to it waits for Codex to finish, and Codex can no longer save into a course on its way to the trash.
- Setup no longer loses courses in the trash of a library at an old location: they move to your library's trash with the rest, and archived courses stay archived.
- The address that opens Throughline no longer contains your key. The launcher signs your browser in with a code that works once, and the key is replaced when you update, since earlier versions wrote it to a log file. Open Throughline from its launcher once after updating.

## 0.54.0

- Look after your courses from the library: each course has a **⋯** menu beside Open, with **Rename**, **Archive** and **Delete…**. Renaming changes the title you see; the course stays where it is and keeps its Studio chats.
- **Archive** a course you are done with to take it out of the list and the course switcher. Nothing in it changes: find it under **Archived courses** below the list, where you can still open it or unarchive it.
- **Delete** asks first, right on the card, then moves the course to the trash with its progress, notes and questions. **Undo** brings it straight back, and **Deleted courses** below the list restores it later. Throughline never empties the trash; to free the space, delete folders from it yourself (**Show the trash folder** opens it). A course that is writing a lesson or that Studio is working on waits until it is done.
- Skipping a chapter, deleting a note, removing a highlight that has a note and deleting something from How you're taught now ask for confirmation right where you clicked, instead of in a browser popup.
- When Codex stops right as a lesson starts, because it isn't signed in say, the message now says what Codex reported instead of "Broken pipe".

## 0.53.2

- The library notices every change to a course's title, route or sources, also two made within a moment of each other. Before, such a change could go unseen until the course changed again.
- Going to another section right after a side question is answered no longer shows an error in the page.

## 0.53.1

- Running an older and a newer Throughline side by side, or going back a version, no longer loses settings the newer one saved: your teacher settings, Studio's access and chats, dismissed tips, and a course's preferences.
- Throughline now installs only versions of the libraries it runs on that it is known to work with, so a future release of one of them can't break it.

## 0.53.0

- When a lesson can't start because of Codex, the message now says what to do: your usage limit is reached, Codex isn't signed in, there's no internet connection, or your account can't use the chosen model. When Codex isn't installed, it says how to install it.
- Throughline now keeps a log of problems in your library's `.throughline/host.log`, with what Codex reported when it failed. The log never grows past a few megabytes. `guided-learning doctor` shows where it is, along with your system and Python version, which helps when you report a problem.

## 0.52.0

- Only you can use Throughline on your computer. It now opens with a key that only your account can read. Other people's programs on a shared computer can no longer read your courses or start Codex through it. Open Throughline from its launcher or with `guided-learning open` as before. A browser opened another way shows how to get in.
- On Windows, Studio no longer gives Codex full access by itself when Codex's sandbox isn't set up. It asks first: set the sandbox up once (Windows may ask for permission), or choose Full access.
- On a Mac, a link in Studio to an app or installer shows it in Finder instead of starting it.
- On Windows, no other program can take over the port Throughline listens on.

## 0.51.0

- On the Overview, Studio now uses the width of a large screen and reaches the bottom of the window. Its conversation stays in one centred column that is easy to read.
- A document chosen on the Overview's Sources tab opens right there and fills the page, with the list of sources in a column beside it. Links to a source in Studio open there too. The Overview no longer shows the side panel: Source opens the Sources tab, and Questions and Notes take you back to Learn with that panel open.
- The reader's header takes one line: the document, the place in it, and whether it was checked. The note on a location not yet checked opens from its status, and Bookmark and Open original sit with the PDF's page and zoom controls.
- A document you open on the Overview now opens at its cited page when you show it in Learn's panel. A Markdown source no longer scrolls the page around it when it opens.

## 0.50.2

- A PDF in the reader stays on the line you were reading when you zoom it or change the panel's width. Before, it jumped to another place in the document, further the deeper you were in it.
- Zooming a long PDF no longer leaves pages blank: every page in view is drawn again at the new size.

## 0.50.1

- "Back to the passage" in a side question now lands on the passage you asked about and briefly marks it, including a passage from a section you were previewing, from a lesson's check question or from an exercise. Before, a passage from an earlier section took you to the current section instead, and one in a check question or an exercise brought back only roughly where you had been reading.
- An open question now always shows **All questions** under its answers, beside "Back to the passage", to go back to the list. Before, the only way back was the close button in the writing box, which is hidden while the box is empty.

## 0.50.0

- Share a course with someone, or keep a copy, from the course's Overview → **Share**: choose the route alone, the route with the lessons and exercises written so far (never your answers, progress or what the teacher remembers about you), or everything. The file always holds the course's source documents.
- **Import a course** on the library, or drop a `.throughline` file on it, shows what the file holds and asks how to take it: continue where it was left (your own course from another computer, or a backup), start fresh, or start fresh keeping the sender's notes and questions to read. A shared lesson is shown step by step as you study it, with no wait for the teacher, and every section starts unstudied.
- A shared course says what goal it was built for and offers to tell Studio yours. With Full access on, Studio warns that the course came from someone else.
- From the command line: `guided-learning export <course> --level route|lessons|everything` and `guided-learning import <file> --fresh` or `--keep-notes`.

## 0.49.3

- A course made in Studio on the library page now always finds the chat that made it in its own Studio. Before, if the page was reloaded or closed while Codex built the course, or the chat was opened again later, the chat stayed with the library and the course's Studio showed no chats.

## 0.49.2

- When Throughline closes, it now waits for its last check for changes Codex made, so it never quits with a course's database still open.

## 0.49.1

- Changes Codex makes while a lesson is streaming now always show in the open course. Since 0.48.2 one could be missed when Codex saved at the same moment as the app, and the app's own saves could reload the course for nothing.

## 0.49.0

- A figure in a lesson keeps showing the same figure after Codex reads its page again. Before, reading a page again could make an earlier lesson show a different figure from that page, when the new reading listed the figures in another order or added or left one out. Correcting a figure's crop still fixes it in every lesson that shows it.
- Reviews now count a question that tests several sections part by part: a missed part counts against its own section only, and answering the question counts as practice of every section it tests, not just the first.

## 0.48.3

- Attaching two files with the same name in Studio at the same moment no longer deletes one of them; the second is saved as `name (2)`.
- When setup moves courses from where earlier versions kept them, it now waits until Throughline has really let go of each course, and leaves a course it cannot take where it is instead of moving it while open.
- If Throughline stops just as a lesson, a side question or a "remember this" request finishes, what that turn asked course memory to keep is now recorded the next time the course opens, instead of being lost.

## 0.48.2

- Exercises, review sets, course memory and page readings that Codex saves in Studio, or in another Codex session, now show in the open course right away, instead of only after something else reloaded it.

## 0.48.1

- Code in a runnable Python cell can no longer use Throughline itself: it runs in a sealed-off part of the page, so a cell cannot read your course, turn on Studio's Full access or send Codex a message. Cells run as before, numpy and the other packages included.

## 0.48.0

- When a course file moves, or you add your own copy of a file that an imported course already has, Throughline now keeps the existing source, with its page readings and its place in the route, instead of adding a second one. Two copies you register on purpose still stay two sources.

## 0.47.0

- A whole course can be saved to one file and opened again as a new course, with its progress, course memory, notes and sources: `guided-learning export <course>` writes `<course>.throughline`, and `guided-learning import <file>` adds it to the library. Use it to back a course up or move it to another computer; Codex can do it from Studio when asked. The file holds only the course, not Codex's working files, so it is far smaller than the course folder.

## 0.46.0

- Before updating a course to a new storage format, Throughline now keeps a copy of it as it was in the course's `backups/` folder. If an update goes wrong, the copy and the earlier Throughline version bring the course back (see ADR 0007). A course that cannot be copied, on a full disk for example, is not updated.
- One damaged course no longer stops the library from listing the others; it is listed with what went wrong, and Throughline no longer keeps its file open, so on Windows it can be replaced while Throughline runs.
- When the library or a course cannot be loaded, the page says why and offers Try again, instead of waiting forever or staying blank.
- Unsent text (side questions, notes, exercise answers, Studio messages) now stays with its own course, and is kept after the browser is closed.

## 0.45.0

- Installing and updating now fetch the latest release (the `stable` branch) instead of whatever is on `main`, so learners only ever get a version that passed the tests on Linux, macOS and Windows. Each release is tagged, so `@v0.45.0` in place of `@stable` installs a particular version.
- The update check in Settings → About compares with the latest release.
- The license notices of the bundled interface code, including CodeMirror's, now ship inside the installed package.
- On Windows, `guided-learning setup --language zh-CN` no longer stops before the Chinese welcome guide when its output goes to Codex: the command now always writes UTF-8.

## Earlier versions

Versions before 0.45.0 were not tagged; their changes are in the [merged pull requests](https://github.com/keweijun/throughline/pulls?q=is%3Apr+is%3Amerged).
