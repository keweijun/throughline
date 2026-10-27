---
name: throughline
description: Build or change a course from multiple PDFs and notes, then open it in the Throughline learning app. Use when a learner asks to plan a cross-document route, study from their materials, add files to or rebuild a course, continue a course, or open Throughline. Learners invoke it as $throughline from any Codex chat.
---

# Throughline: build courses, then open the app

Throughline is the study app; this skill builds and changes courses and opens them there. The app teaches every lesson, side question and exercise; do not teach the course in this chat (ADR 0004). Talk with the learner in their language, set the course's teaching language to match (see [course operations](references/course-operations.md)), and preserve original source text and existing learning records in their original language.

The `guided-learning` command is the app; the browser interface it opens is the teaching surface. The learner should not need to type commands: run them yourself. If `guided-learning` is not found, ask the learner to install Throughline first (the project README has a prompt to paste) and stop.

To update Throughline when the learner asks: run `guided-learning stop`, then remove the pre-0.5.1 package name (`uv tool uninstall codex-guided-learning` or `pipx uninstall codex-guided-learning`; "not installed" is fine), then `uv tool install --reinstall "throughline[pdf] @ git+https://github.com/keweijun/throughline"` (or `pipx install --force` with the same package), then `guided-learning setup`, outside the sandbox. Courses are kept.

Use the course workspace as the only official state. Courses live in the learner's Throughline folder; the learner may call this skill from any Codex chat or folder, so always address courses by name through the command, never by the current directory; `guided-learning courses` prints its `root` and lists courses by name.

## Prepare a course

Get the learner's materials, then always interview them about goal, prior knowledge, depth and focus in one short message before building the route, even when the goal seems clear (see [course operations](references/course-operations.md)). Create the course, save their profile and teaching language, and register PDFs and Markdown; inspect failures and unreadable pages. Use [curriculum operations](references/curriculum.md) to outline chapters and build them one at a time, giving each section its core question and objective. Show the chapter outline before saving it; after the learner agrees, build without asking again. A candidate map can be used for learning with its uncertainty visible; do not claim complete verification from extraction alone.

Finish every piece of course work (creating a course, adding files, building or rebuilding chapters, reviewing pages) by opening that course in the app as described in [learning app](references/learning-app.md); do not stop at a route summary. An open app tab picks up the changes by itself.

## Existing courses

To continue studying, open the course in the app; do not create a parallel course or replay lessons into it. To answer the learner's questions about their course (where they are, what is open), read `course.status` and `session.resume`; these include questions asked in the app. Never infer mastery from listening to an explanation, seeing a solution, or readiness of preparation material.

If the learner asks to be taught in this chat, explain that lessons, questions and practice now happen in the app, where they are saved with the course, and open it. The chat-teaching operations still work for existing scripts but are deprecated ([reference](https://github.com/keweijun/throughline/blob/main/docs/chat-teaching-operations.md)).
