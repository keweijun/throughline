# Documents are converted to PDF

Learners bring slide decks and Word documents as often as PDFs, but a source could only be Markdown or PDF. A source needs two things: text the teacher can read and cite by location, and a view that shows the learner the cited place as the author laid it out (ADR 0004: the original page beside the explanation).

## Decision

The host reads two kinds of file:

- **PDF**, by page, with the page image and the original file in the reader.
- **Text**: any file in UTF-8 (with or without a byte order mark) or UTF-16 with one, by line, in the line reader. Markdown, plain text, LaTeX, code and CSV need nothing else. Text in another encoding is refused so its lines are never misread.

Every other document is converted to PDF by **Codex**, with whatever the learner's computer has: Microsoft Office driven from PowerShell on Windows, LibreOffice headless anywhere, Pages and Keynote through AppleScript, Calibre for EPUB, or an install of LibreOffice the learner agrees to. Codex keeps the original in the course's `inputs/`, writes the PDF to `inputs/converted/`, checks it against the original, and registers the PDF with `converted_from`, the original's path. The source record and its snapshot keep `converted_from: {path, revision}`, the original's SHA-256 at conversion, and the reader names the original. Office and similar formats registered directly are refused with an error that says to convert them.

Speaker notes are lost in a PDF export of slides, and in lecture decks they often hold the explanation. When a deck has notes, Codex also writes them to a Markdown file beside the PDF, one `## Slide N` heading per slide with notes, registered with the same `converted_from`. The slides keep their normal layout, and the teacher can cite both.

## Considered

- **The host converts.** The host would run LibreOffice itself on registration and store the PDF next to the snapshot. That ties a source to one converter, cannot use Office where it renders the document best, and needs a second stored file per revision and a migration. Codex already runs on the learner's computer, can find and drive what is installed, and can check the result and say what was lost.
- **Text extraction only** (python-pptx, python-docx), with no rendered view. The teacher could read the document, but the learner could not see the slide or page being taught, which the reader exists for.
- **Notes-page PDF export**, keeping speaker notes in the PDF. Each slide shrinks to a part of the page, and the notes' text mixes with the slide's in extraction.

## Consequences

A converted source is a PDF in every other respect: citations, highlights, coverage and verification work unchanged, and a course made before needs no migration, since `converted_from` is optional. The host does not watch originals, as it does not watch any source: when the learner updates one, Codex converts and registers again, and `converted_from.revision` tells it whether a conversion is out of date. A learner without Office or LibreOffice needs one install or a PDF exported by hand.
