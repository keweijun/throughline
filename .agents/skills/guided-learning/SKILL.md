---
name: guided-learning
description: Build and resume a personal course from multiple local documents, preserving sources, teaching position and learning evidence across chats.
---

# Guided learning

Teach in English by default. Follow explicit learner requests for another language, and preserve original source text and existing learning records in their original language.

Use the course workspace as the official state. Keep course files outside tracked code (for example `work/courses/<name>`). On entering an existing course, read its status before teaching; recover its saved goal and next step rather than infer them from the latest message.

For course creation, material registration, source retrieval and saving a position, read [course operations](references/course-operations.md). The operation entrypoint persists each request transactionally. Read failures and pending verification are visible outcomes to report to the learner. Extracted text alone does not establish complete content coverage or formula/image accuracy.

Save the current goal, explanation progress and next step before leaving the main teaching line or ending a session. Registration retains exact source bytes by revision; Markdown line numbers and PDF page numbers are distinct locators. Preserve this distinction when citing material.

For cross-document concepts, prerequisite routes, notation/exercise mappings, coverage auditing and focused teaching context, read [curriculum operations](references/curriculum.md).

When teaching, handling a sidequestion or resuming a session, read [teaching operations](references/teaching.md). Record actual interactions and use route context to choose response depth; optional background work does not block the explanation.

For section-end practice, assessment of learner evidence, deferral or review, read [evidence operations](references/evidence.md).

After a small section, if optional note consolidation is useful, read [background jobs](references/background.md). Use an available host Luna subagent with minimal context; preserve pending work when unavailable and keep foreground teaching independent.
