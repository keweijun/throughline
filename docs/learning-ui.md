# Using the learning interface

Start the host from the project root and open http://127.0.0.1:8765:

```sh
.venv/bin/python -m guided_learning.web --workspace work/courses/quantum-v1
```

Keep the terminal open; Ctrl+C stops the host. Choose English (default) or Simplified Chinese with the language selector in the top bar. The selection is course-owned and survives browser reloads and host restarts. It updates interface text without discarding input drafts, while sources and saved records keep their original language.

New lessons, side answers, supplements, exercises, feedback and preparation use the selected teaching language. Running requests finish in their original language; regenerating an incomplete reply uses the current selection and retains the earlier attempt. Changing language invalidates previous-language preparation without changing the teaching position or mastery evidence.

## Learning

- **Route** (left): your current section is marked "You are here". Selecting another section previews it without moving your learning position; "Back to current section" returns.
- **Start lesson**: the first lesson of a section opens with a unit overview and then teaches directly. Text streams in and is saved automatically when complete. "Ask for another pass" requests a new lesson in the same section.
- **Side questions**: select a sentence or formula in a lesson and choose "Ask about this passage", or open Questions in the top bar. The lesson keeps going unless you tick "Pause the lesson while I ask". Passages you asked about stay highlighted. If the teacher suggests studying a foundation first, you decide; "Return to the lesson" scrolls back to where you asked.
- **Sources**: citation buttons in lessons open the exact registered revision in the Source tab: the extracted line for Markdown, a rendered page image plus the original PDF for PDFs. "Pending verification" stays visible even when the model cites the source.
- **Practice**: exercises are prepared after a lesson completes. "Check my answer" asks the teacher to assess; Hint, Key steps and Full solution are always available, but after any help a correct answer is recorded as solved with help, not on your own. "Do later" keeps an exercise open; open exercises from earlier sections follow you.
- **Enter next section** moves your position; practice is optional.
- **Preparation**: while nothing else runs, the next section is prepared in the background. Prepared material is teacher-only and never counts as learning. Your own requests always take priority.

## Model settings

Choose the teacher in Model settings: Local Codex CLI (default) or any OpenAI-compatible provider (OpenAI, OpenRouter, Ollama, LM Studio, vLLM and others). Keys can be stored or read from an environment variable; they stay in your user config directory and are never shown in the browser. `--provider` and `--model` override the saved choice for one run.

## Pause, close and reopen

"Pause" stops generation and keeps the partial text as unfinished. "Regenerate" keeps the earlier attempt (under "Earlier unfinished attempts") and writes a complete new reply rather than continuing mid-sentence. If the model is still stopping, wait a moment and try again.

Closing the browser does not stop the host; work in progress continues. Stopping the host stops all model work. On reopen, the saved records return and any request cut off by the stop is shown as interrupted. Only one host can own a course at a time.

To move a course to another machine, stop the host and copy the whole course directory, including `course.sqlite3` and `sources/`.

## Troubleshooting

- **Port in use**: pass `--port`. If the course already has a host, use that window instead of starting a second one.
- **Model errors**: the lesson shows the provider's message. For Codex, check the CLI's configuration in a terminal. For OpenAI-compatible providers, check the base URL, model name and key in Model settings ("Load available models" tests the connection). Partial text is kept.
- **Page image unavailable**: install the `pdf` extra in the same environment, or use the original PDF link.
- **Preparation failed**: choose "Retry preparation"; learning continues without it.
- **"Reconnecting"** in the top bar: the browser lost the live connection. Your work is saved; it reconnects automatically once the host is reachable.
