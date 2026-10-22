---
name: guided-learning
description: Build or resume a course from multiple PDFs and notes, then open its local learning UI. Use when a learner asks to plan a cross-document route, study from their materials, continue a course, or launch the guided-learning app.
---

# Guided learning

Teach in English by default. Follow explicit learner requests for another language, and preserve original source text and existing learning records in their original language.

The `guided-learning` command is the app; the browser interface it opens is the teaching surface. The learner should not need to type commands: run them yourself. If `guided-learning` is not found, ask the learner to install Guided Learning first (the project README has a prompt to paste) and stop.

Use the course workspace as the only official state. Courses live in the learner's course library; `guided-learning courses` lists them by name. On entering an existing course, read its status before teaching; recover its saved goal and next step rather than infer them from the latest message.

## Prepare a course

Confirm the learner's goal and the paths to their materials. If these are already clear, proceed. Create the course and register PDFs and Markdown with [course operations](references/course-operations.md); inspect failures and unreadable pages. Use [curriculum operations](references/curriculum.md) to build a source-linked concept route and coverage ledger. Show the proposed route and unresolved source checks. A candidate map can be used for learning with its uncertainty visible; do not claim complete verification from extraction alone.

When the learner wants the app, open the course as described in [learning app](references/learning-app.md). Open it after preparing the route when their request includes starting to study; do not stop at a route summary. The browser owns the interactive lesson, questions, practice, and progress display.

## Resume or teach in chat

For an existing course, use `session.resume` to recover position, due explanations and open questions. If the learner wants the UI, open the same course; do not create a parallel course or replay previous lessons into it. If the learner explicitly chooses teaching in chat, read [teaching operations](references/teaching.md), record actual interactions, and preserve the mainline. Use [evidence operations](references/evidence.md) for real practice and deferral. Optional [background jobs](references/background.md) may consolidate notes without blocking the learner.

Save the current goal and next step when teaching in chat. Registration retains source bytes by revision; Markdown lines and physical PDF pages are different locators. Never infer mastery from listening to an explanation, seeing a solution, or readiness of preparation material.
