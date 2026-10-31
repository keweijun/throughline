---
name: throughline
description: Build or change a course from PDFs, slides, documents and notes, then open it in the Throughline learning app. Use when a learner asks to plan a cross-document route, study from their materials, add files to or rebuild a course, continue a course, or open Throughline. Learners invoke it as $throughline from any Codex chat.
---

# Throughline: build courses, then open the app

Throughline is the study app; this skill builds and changes courses and opens them there. The app teaches every lesson, side question and exercise; do not teach the course in this chat (ADR 0004). Talk with the learner in their language, set the course's teaching language to match (see [course operations](references/course-operations.md)), and preserve original source text and existing learning records in their original language.

The `guided-learning` command is the app; the browser interface it opens is the teaching surface. The learner should not need to type commands: run them yourself. If `guided-learning` is not found, ask the learner to install Throughline first (the project README has a prompt to paste) and stop.

To update Throughline when the learner asks: run `guided-learning stop`, then remove the pre-0.5.1 package name (`uv tool uninstall codex-guided-learning` or `pipx uninstall codex-guided-learning`; "not installed" is fine), then `uv tool install --reinstall "throughline[pdf] @ git+https://github.com/keweijun/throughline"` (or `pipx install --force` with the same package), then `guided-learning setup`, outside the sandbox. Courses are kept.

Use the course workspace as the only official state. Courses live in the learner's Throughline folder; the learner may call this skill from any Codex chat or folder, so always address courses by name through the command, never by the current directory; `guided-learning courses` prints its `root` and lists courses by name.

## Prepare a course

Lead the intake rather than wait for instructions, following [course operations](references/course-operations.md): read the materials first, read back what they contain, and always interview the learner about goal, prior knowledge, depth, focus and how they like to learn, even when the goal seems clear, offering concrete options with one recommended so a word or "ok" answers. Offer a quick check of the prerequisites the route leans on, and offer route options when the materials allow real alternatives. Create the course, save their profile, teaching language and learning preferences, select the teaching add-ons the subject calls for, and register PDFs and text files, converting other documents such as Word and PowerPoint to PDF first; inspect failures and unreadable pages. Use [curriculum operations](references/curriculum.md) to outline chapters and build them one at a time, giving each section its core question and objective. Show the chapter outline before saving it; after the learner agrees, build without asking again. A candidate map can be used for learning with its uncertainty visible; do not claim complete verification from extraction alone.

Finish every piece of course work (creating a course, adding files, building or rebuilding chapters, reviewing pages) by opening that course in the app as described in [learning app](references/learning-app.md); do not stop at a route summary. An open app tab picks up the changes by itself.

In Throughline Studio, the app's own Codex chat (its developer instructions say so), the app is already open: never run `guided-learning open` or `guided-learning stop`, and finish course work by saying what changed and naming the course instead. Files the learner attaches there are already copied into the course's `inputs/` folder; register them where they are rather than copying them again. When a Studio chat names an open course, work on that course unless the learner says otherwise.

## Existing courses

When the learner adds files to a course, read them first, say what they add, and propose where they fit (a new chapter, exercises for sections already built, a revision of a chapter), recommending one; reordering the route still needs their agreement. To continue studying, open the course in the app; do not create a parallel course or replay lessons into it. To answer the learner's questions about their course (where they are, what is open), read `course.status` and `session.resume`; these include questions asked in the app. Never infer mastery from listening to an explanation, seeing a solution, or readiness of preparation material.

If the learner asks to be taught in this chat, explain that lessons, questions and practice now happen in the app, where they are saved with the course, and open it. The chat-teaching operations still work for existing scripts but are deprecated ([reference](https://github.com/keweijun/throughline/blob/main/docs/chat-teaching-operations.md)).
