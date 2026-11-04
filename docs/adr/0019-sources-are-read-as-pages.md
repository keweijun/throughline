# Sources are read as pages, and the reading is the verification

A PDF source was its extracted text (pypdf), one unit per page, marked `verification: pending` until Codex checked it. Extraction loses what textbooks and slides carry most: formulas come out as scrambled symbols, tables lose their columns, two-column pages interleave, scanned and handwritten pages are empty, and figures disappear. The teacher taught from that text, and the later check rarely happened, so most pages stayed `pending` for the life of a course. The teacher also never saw a figure, and a lesson could not show one: a diagram the explanation depends on was only reachable by opening the cited page in the reader.

## Reading every page while building the course

Codex now **reads each page of a PDF source as an image** when the source is registered, before chapters are built, and records a **page reading**:

- `text`: a faithful Markdown transcription in the source's own language, formulas in LaTeX, tables as tables, in reading order, handwriting included.
- `figures`: each figure, diagram, chart or photograph on the page that teaching may point to, with its `label` as printed ("Figure 3.2", or none), `caption`, a `description` the teacher can read without seeing it, and `box`, where it sits on the page as fractions of the page's width and height.
- `problems`: what could not be read, with the reason (illegible, cut off, a page missing from the sequence).

A page with a reading is verified: the reading is the check against the page, so `verification: verified` no longer waits for a separate pass. A page reading is source fidelity, not coverage: mapping a page to a concept still says nothing about whether the concept teaches all of it (the coverage ledger keeps its own `verification`). Text sources are already exact and are not read.

The extracted text stays in the immutable snapshot. Search and highlight positions keep using it, and it is the fallback for a page without a reading. Where a page has a reading, the teacher's source excerpts use the reading.

## Codex organizes the reading

The skill states the goal (every page of every registered PDF has a reading before its chapter is built) and leaves how to get there to Codex. Codex may read several pages in one look, use its subagents to read parts of a long source in parallel, and give a dense page more attention than a title slide. The host adds tools and keeps the record:

- `source.render` renders pages, or a box on a page, to image files Codex can view, at a scale it chooses. Codex also uses it to check a figure's box by looking at the crop.
- `source.readings.save` stores readings for any set of pages of one revision, checking pages and boxes. Each page is its own record, so subagents saving at the same time never overwrite one another, and saving a page again replaces its reading.
- `source.read` reports which pages have readings, so Codex, and the learner in Studio, can see what is still unread.

The interview does not wait for the reading: the read-back and the chapter outline use the extracted text, as before, and a chapter is built once its own pages are read.

A host-run job was considered: the host splits pages into fixed batches and runs parallel read-only turns, with progress in the app, retries and resumption after a restart. It was rejected because fixed batches rule out what the model does better on its own: deciding how many pages to read at once, which pages need a closer look and how to divide the work. Coverage is visible through `source.read` instead of enforced.

## Figures in lessons

A **figure** is a region of a source page that a lesson shows. An add-on fence names it by source, page and figure index, and the interface draws the crop from the page render with its caption and a link to the page in the reader. The box belongs to an immutable revision, so no image is extracted or stored. Like every widget (ADR 0013), a figure that cannot be drawn shows its source, and the Notes export shows the label and page. The teacher reads figure descriptions with its source excerpts and may receive a figure's crop as an image input on a turn about it, never in the developer instructions, which the prompt cache keeps stable.

## Consequences

- Building a course costs one look at every page, a large one-time cost for a long source, paid in the learner's Codex usage. Parallel reading can meet rate limits; Codex adapts, and unread pages stay visible.
- The reading is checked by the model that makes it, with no independent second pass, as with the teacher's other judgments. The original page stays one citation away, and a disputed page is read again.
- In-app chapter builds run read-only and cannot render pages; they use readings made in Codex or Studio and fall back to extracted text.
- Readings are an additive record per source revision, read as absent, so courses need no migration (ADR 0007). Existing courses keep `pending` pages until the learner asks Codex to read them, which is course work in Studio.
- A new revision of a source has no readings until its pages are read again. Readings for an unchanged page could be copied by comparing page renders; that is not done yet.
- This amends ADR 0015, where verification "works unchanged" for converted sources: a converted PDF is read like any other.
