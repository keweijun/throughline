# Teaching widgets: built-in basics and per-course add-ons

Lessons were Markdown with LaTeX, and nothing else was drawn. Teachers explain processes, state machines, graphs of functions and chemical reactions in prose that a drawing would make clearer, and the material differs by subject: a calculus course wants function graphs, a chemistry course wants reaction equations, a programming course wants highlighted code.

A **teaching widget** is part of a lesson's Markdown that the interface draws: a fenced code block tagged with the widget's language, or notation inside a formula. Stored lessons stay plain Markdown, so the Notes export (ADR 0005) and any Markdown viewer keep the source, and a widget the interface cannot draw shows its source.

## Basics and add-ons

- **Basic widgets** are useful in every subject and cost little prompt: LaTeX, code fences highlighted by language, callouts (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`) and Mermaid diagrams. The teacher instructions always describe them.
- **Add-ons** serve particular subjects. They live in a library inside this repository (`guided_learning/widgets.py`), each with a summary and subjects for choosing it and a guide for the teacher. The first are `plot` (graphs of functions of x), `chemistry` (mhchem) and `python` (runnable Python cells, below).
- **Codex selects a course's add-ons** while building it (`widgets.save`) and may change the selection later. Only the selected add-ons' guides enter the teacher's instructions, so a large library does not grow every prompt. The selection is stable across a course's turns, so the guides go in the developer instructions that the prompt cache reuses.
- **The interface renders every add-on in every course.** The selection decides what the teacher is told, not what the interface can draw, so removing an add-on never breaks a lesson written with it. Removing an add-on from the library does: its lessons show their source. Treat a shipped fence language as permanent.
- Add-ons are code reviewed in this repository, never third-party plugins: a renderer runs on the learner's page.

## For the learner

Add-ons stay out of the interface: there is no list or toggle in Settings or on the course page (Settings stays simple; teaching style goes through course memory, ADR 0010). When showing the chapter outline, Codex may say in plain words how the course will use them ("I'll graph the functions in chapters 2–4"). A learner who asks for more or fewer drawings changes the teaching through conversation and course memory; Codex changes the selection itself. A drawing the library cannot make is described in words.

## Consequences

- Libraries load on first use, so the interface bundle barely grows; the package ships Mermaid's diagram chunks. Mermaid's optional ELK layout (EPL-2.0, 1.4 MB) is replaced by its default layout at build time.
- A diagram or plot is drawn once its fence closes; while a lesson streams, the source shows until then.
- The selection is an additive course record (`course/widgets`), read as empty when absent, so courses need no migration (ADR 0007). An older Throughline opening a course shows add-on fences as source.

## Runnable Python

The `python` add-on draws a `python-run` fence as a cell: the fence's code in an editor, with Run, Stop, Reset and the output below. In a lesson the learner runs and changes examples; in an exercise the starter code marks what to complete, and **Add to answer** puts the code and its output in the answer box. Running code never decides an outcome: there are no automatic tests, and the teacher assesses the submitted answer by part like any other (ADR 0002, ADR 0011).

- Code runs in the browser with Pyodide (Python 3.14), pinned to one release and loaded from jsDelivr on the first Run, then from the browser's cache. It is not shipped in the package, which would add tens of megabytes for courses that never run code; offline, the cell says Python could not load. This is the one add-on that loads code from outside the app, so it runs in a Web Worker, never on the learner's page.
- The worker also lets Stop end an endless loop without freezing the page. Each run starts with fresh globals, so cells never share variables. Packages Pyodide offers (numpy, scipy, sympy, pandas and others) load from the code's imports. Output is text only; `input()` fails rather than waiting.
- The cell is a custom element whose editor lives in a shadow root and whose own markup never changes, so the Markdown patcher keeps it, with what the learner typed, when a lesson is drawn again. Keys typed in it stay in it rather than reaching the app's shortcuts.
