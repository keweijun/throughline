---
name: throughline
description: Build or resume a course from multiple PDFs and notes, then open its local learning UI. Use when a learner asks to plan a cross-document route, study from their materials, continue a course, or open Throughline. Learners invoke it as $throughline from any Codex chat.
---

# Throughline: guided learning

Teach in English by default. Follow explicit learner requests for another language, and preserve original source text and existing learning records in their original language.

The `guided-learning` command is the app; the browser interface it opens is the teaching surface. The learner should not need to type commands: run them yourself. If `guided-learning` is not found, ask the learner to install Throughline first (the project README has a prompt to paste) and stop.

To update Throughline when the learner asks: run `guided-learning stop`, then `uv tool install --reinstall "codex-guided-learning[pdf] @ git+https://github.com/keweijun/throughline"` (or `pipx install --force` with the same package), then `guided-learning setup`, outside the sandbox. Courses are kept.

Use the course workspace as the only official state. Courses live in the learner's Throughline folder; the learner may call this skill from any Codex chat or folder, so always address courses by name through the command, never by the current directory; `guided-learning courses` prints its `root` and lists courses by name. On entering an existing course, read its status before teaching; recover its saved goal and next step rather than infer them from the latest message.

## Prepare a course

Confirm the learner's goal and the paths to their materials. If these are already clear, proceed. Create the course and register PDFs and Markdown with [course operations](references/course-operations.md); inspect failures and unreadable pages. Use [curriculum operations](references/curriculum.md) to build a source-linked concept route and coverage ledger. Show the proposed route and unresolved source checks. A candidate map can be used for learning with its uncertainty visible; do not claim complete verification from extraction alone.

Finish every piece of course work (creating a course, adding files, rebuilding a route, reviewing pages) by opening that course in the app as described in [learning app](references/learning-app.md); do not stop at a route summary. An open app tab picks up the changes by itself. The app owns the interactive lesson, questions, practice, and progress display.

## Resume or teach in chat

For an existing course, use `session.resume` to recover position, due explanations and open questions. If the learner wants the UI, open the same course; do not create a parallel course or replay previous lessons into it. Studying belongs in the app; teach in chat only when the learner explicitly asks for it. Then read [teaching operations](references/teaching.md), record actual interactions, and preserve the mainline. Use [evidence operations](references/evidence.md) for real practice and deferral. Optional [background jobs](references/background.md) may consolidate notes without blocking the learner.

Save the current goal and next step when teaching in chat. Registration retains source bytes by revision; Markdown lines and physical PDF pages are different locators. Never infer mastery from listening to an explanation, seeing a solution, or readiness of preparation material.
