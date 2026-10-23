# Using the learning interface

Open Throughline from its launcher, or ask Codex to open a course (`guided-learning open <course>`); the interface runs in the background until `guided-learning stop`. It opens on **Your courses**, the course library; **Courses** in the top bar returns to it. For a course outside the library, run `guided-learning-web --workspace path/to/course` and keep the terminal open; Ctrl+C stops it. Choose English (default) or Simplified Chinese under Language in **Settings** (the gear in the top bar), which also holds Appearance (light, dark or matching the system) and the Teacher settings. The selection is course-owned and survives browser reloads and host restarts. It updates interface text without discarding input drafts, while sources and saved records keep their original language.

New lessons, side answers, supplements, exercises, feedback and preparation use the selected teaching language. Running requests finish in their original language; regenerating an incomplete reply uses the current selection and retains the earlier attempt. Changing language invalidates previous-language preparation without changing the teaching position or mastery evidence.

## Learning

- **Route** (left): your current section is marked "You are here". Selecting another section previews it without moving your learning position; "Back to current section" returns. A section shows "saved questions" when earlier questions are waiting for their full explanation there.
- **Goal and next step**: the top of the current section shows its goal and what to do next, following what has actually happened: start the lesson, follow it while it is written, try the open exercises, or move on. "Where you left off" appears when the course has a progress note.
- **Start lesson**: the first lesson of a section opens with a unit overview and then teaches directly. Text streams in and is saved automatically when complete. "Ask for another pass" requests a new lesson in the same section.
- **Side questions**: select a sentence or formula in a lesson and choose "Ask about this passage", or open **Questions** in the top bar. The lesson keeps going unless you tick "Pause the lesson while I ask". Passages you asked about stay highlighted, with a marker in the margin that opens the question. If the teacher suggests studying a foundation first, you decide. "Back to the passage" (or "Return to the lesson" for a question without a quoted passage) scrolls to what you asked about, even if the page has reflowed; it appears only while you are still in the section you asked from.
- **Many questions**: each question shows as a summary (status, section, follow-ups, notes); select it or its arrow to open the thread. With three or fewer questions all are open; otherwise only one being answered opens by itself. The list shows this section's questions (or all when this section has none); switch to **All** or search question and answer text. Opening a question from a margin marker or saved explanation finds it whatever the filter.
- **Pending explanations**: when a question is answered briefly because a later section covers it properly, the thread says which section and links to it. That section lists the question under "Saved for this section", its lesson gives the full explanation, and the question is then marked "Explained".
- **Set aside for now**: the section overview lists source material the course plan deferred or flagged for review, with the reason, so nothing silently disappears from the route.
- **Sources**: hover over a citation to see the cited text. **Source** in the top bar shows or hides the reader. Click a citation to open the exact registered revision in the built-in reader: PDFs open at the cited page (outlined, with "Back to cited page" if you scroll away), with selectable text, zoom and fit-to-width; Markdown notes open at the highlighted line. Select text in the reader to ask about it. **All sources** in the reader header (or the Source tab before anything is open) lists every document in the course, those used by the section you are reading first, with their status and sections; choosing one opens it where this section uses it. "Pending verification" stays visible even when the model cites the source. Drag the panel's left edge (or focus it and use the arrow keys) to resize it.
- **Highlights, notes and bookmarks**: select text in a lesson, a side-question answer, an exercise (its question or the teacher's feedback) or the source reader and choose **Highlight** or **Note**. Question threads and exercises with notes show a "1 note" button that opens them. Your highlights are green; asked passages stay yellow. A pencil marker in the lesson margin opens the note. **Bookmark section** (next to the section number) and **Bookmark page** (in the source reader) mark places to come back to; bookmarked sections show a star in the route. **Notes** in the top bar (or `n`) lists everything for this section or all sections, where you can edit, delete, jump back, or add a note to the whole section. These are yours alone: the teacher never sees them, and they do not count as progress. To get the teacher's view on something, ask a side question.
- **Practice**: exercises are prepared after a lesson completes. "Check my answer" asks the teacher to assess; Hint, Key steps and Full solution are always available, but after any help a correct answer is recorded as solved with help, not on your own. "Do later" keeps an exercise open; open exercises from earlier sections follow you.
- **Enter next section** moves your position; practice is optional. Exercises not yet solved, including ones that need another try, stay open and follow you.
- **Changing the course**: the course is built and changed in Codex. Below the route, "Add files in Codex" (and "Review … in Codex" when locations still need checking) opens a new Codex chat in your Throughline project with the request typed in; an unchecked source location offers "Review this location in Codex". Each of these also copies the request, so with the Codex CLI you can paste it into Codex started in your Throughline folder. The page updates by itself when Codex is done.
- **Preparation**: while nothing else runs, the next section is prepared in the background; its status is shown in the "Up next" card. Prepared material is teacher-only and never counts as learning. Your own requests always take priority.

## Teacher settings

The teacher is the Codex CLI on this computer. In **Settings**, under Teacher, choose the model (empty means your Codex default) and reasoning effort. `--model` and `--effort` override the saved choice for one run.

## Keyboard shortcuts

`/` ask a side question · `[` and `]` previous and next section · `s` show or hide the source reader · `n` show or hide your notes · `?` list the shortcuts · `Esc` close the route drawer, or the side panel when it covers the lesson.

## Pause, close and reopen

"Pause" stops generation and keeps the partial text as unfinished. "Regenerate" keeps the earlier attempt (under "Earlier unfinished attempts") and writes a complete new reply rather than continuing mid-sentence. If the model is still stopping, wait a moment and try again.

Closing the browser does not stop the host; work in progress continues. Stopping the host stops all model work. On reopen, the saved records return and any request cut off by the stop is shown as interrupted. Only one host can own a course at a time.

To move a course to another machine, stop the host and copy the whole course directory, including `course.sqlite3` and `sources/`.

## Troubleshooting

- **Port in use**: pass `--port`. If the course already has a host, use that window instead of starting a second one.
- **Model errors**: the lesson shows the message. Check that `codex` runs in the same terminal and that the model in Settings is available to your Codex account. Partial text is kept.
- **A PDF does not display**: use "Open original" in the reader header.
- **Preparation failed**: choose "Retry preparation"; learning continues without it.
- **"Reconnecting"** in the top bar: the browser lost the live connection. Your work is saved; it reconnects automatically once the host is reachable.
