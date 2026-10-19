# Learning interface usage and recovery

From the project root, install `python -m pip install -e ".[pdf]"` using the project virtual environment, then run:

```powershell
.\.venv\Scripts\python.exe -m guided_learning.web --workspace work/courses/quantum-v1 --port 8765 --model gpt-6.1-sol --effort medium
```

The host listens only on loopback; open [the interface](http://127.0.0.1:8765). Keep the terminal open; Ctrl+C stops it. No Node build or CDN is needed: Markdown, KaTeX, DOMPurify, and WOFF2 fonts are bundled. Codex CLI must be on PATH with a configured provider supporting the requested model. PDF rendering uses pypdfium2/Pillow from the `pdf` extra.

The UI and teaching default to English. Explicitly request another language in your lesson or question prompt when needed. Sources and saved learning records keep their original language.

## Learning

- Left-side concepts preview without moving the mainline; the central goal and section state show your position. The first lesson begins with a concrete unit overview and then teaches directly.
- Text streams and saves automatically. Taught content and mastery remain separate; the teacher does not need to write a second script.
- Select a sentence/formula and click "Ask about this passage," or open "Side questions." Ordinary questions preserve the mainline. Choose whether to accept foundation supplements and return to the original goal afterward.
- Source buttons open the exact registered PDF revision. Pending verification stays pending even when a model cites it.
- Exercises are prepared at section completion. Freely request hints, steps, or full solutions. "Do later" retains pending work; you choose "Enter next section." Correct answers after viewing a solution or receiving help are not independent mastery.
- Next-section preparation runs when idle. Teaching, questions, and practice take priority; failed preparation does not block the teacher from preparing independently. Ready means internal material is available.

## Pause, close, and reopen

"Pause" stops the current generation request, retaining partial text as unfinished. "Regenerate section" retains the old attempt and starts a complete new lesson rather than continuing from a character offset. Wait for model cancellation to finish before retrying.

Closing the browser does not stop the host; generation/preparation can continue while the terminal runs. Closing the host stops background work. Reopening the same workspace restores official records and marks unexpectedly interrupted requests without completing partial lessons. Only one host may own a course.

To change machines, copy the full course directory, including `course.sqlite3` and revision snapshots under `sources`, after stopping the host. Materials, state, and model logs are outside Git.

## Troubleshooting

- Port occupied: change `--port` and use its URL. If the course already has a host, return to that window rather than starting a second host.
- Model failure: check the terminal's Codex configuration. Failed state and partial text are retained; inspect before repeated retries. The app does not change authentication.
- Page image unavailable: reinstall `.[pdf]` in the same environment or use the original PDF link.
- Preparation failure: retry explicitly in the UI; learning can continue without it.
- Report problems with the action, visible state, and error text. Keep configuration secrets out of reports.
