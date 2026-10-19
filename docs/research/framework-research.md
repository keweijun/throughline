# Long-term multi-document guided learning: product review

Review date: 2026-10-12 (user timezone). These are historical official-document/repository checks, not installed-product tests. Unconfirmed does not mean absent. The target is a recoverable, testable learning route with gap checks spanning six lectures and two exercise documents.

## DeepTutor: documented capability versus actual experience

The user tried Mastery Path, encountered inadequate cross-document guidance and document-reading failures, and stopped exploring. That direct experience cannot be replaced by feature descriptions.

Official [Mastery Path](https://docs.deeptutor.info/explore/mastery-path/) describes multi-file selection, editable modules/concepts, missing-file checks, mastery gates, spaced review, and resumed conversations. Multi-file selection alone does not establish duplicate merging, cross-lecture prerequisites, or sustained evidence-based teaching. Those abilities and reliable source reading remain unverified; DeepTutor is a conditional candidate.

Historical release notes list source-completeness improvements in v1.6.4 (2026-09-03) and background Task Model in v1.6.1 (2026-08-30). The README at review time listed v1.6.14 (2026-10-08) as latest: [release/feature history](https://github.com/HKUDS/DeepTutor/blob/main/README.md).

[Settings](https://docs.deeptutor.info/explore/settings/) configures a separate background Task Model. [Memory](https://docs.deeptutor.info/explore/memory/) describes workspace entities, partition summaries, cross-partition synthesis, and inspectable sources. Documentation does not establish that all memory updates leave the critical response path or that all formulas, images, and exercise types receive page-level coverage.

## Five candidates

| Candidate | Documented capabilities | Gaps or checks for this use | Suggested role |
|---|---|---|---|
| DeepTutor | Multi-source paths, concept types, mastery gates, spaced review, resume, background model | User encountered reading/guidance failures; fusion, prerequisites, and reliability unproven | Reevaluate after evidence of relevant fixes |
| RemNote | Guided Learn from files, documents, or knowledge-base folders; sections, questions, cards, quizzes, Mastery Tracker | Source/chapter emphasis; automatic merging into a prerequisite graph unconfirmed; initial level changes activity priority rather than generated content | Small interface/review trial, not a proven complete solution |
| OpenMAIC | Slides, quizzes, simulations, whiteboard, AI teacher/peers, stage-specific models, course/session persistence | Cross-course mastery, coverage audits, long-term spaced review unconfirmed; persistent generation is not long-term teaching policy | Interactive-classroom/physics visualization layer |
| NotebookLM | Multi-source questions, citations, Learning Guide, cards/quizzes | Explicit prerequisites and evidence-based long-term scheduling unconfirmed; notebooks cannot jointly read each other, so put all eight documents together | Source-reading/retrieval comparison |
| LearnHouse | Course → chapter → activity; Trails completion/quizzes; current-course/activity AI context | Completion/scores are not conceptual mastery; automatic fusion and long-term adaptive scheduling unconfirmed | Course delivery to groups, heavier for personal use |

RemNote evidence: [Guided Learn](https://help.remnote.com/en/articles/15724936-guided-learn-mode) and [Reader](https://help.remnote.com/en/articles/6690975-learning-from-pdfs-and-files-with-the-remnote-reader). The reader places source, notes, and learning tools alongside each other. At review time AI used credits and the reader was mainly a Pro feature.

OpenMAIC evidence: [official repository](https://github.com/THU-MAIC/OpenMAIC). Distinguish versions: 1.2.0-rc.1 (2026-10-04) was prerelease, moving generation to a persistent server with PostgreSQL/service requirements. Main-branch capabilities are not automatically stable-release capabilities. Multiple AI roles do not automatically reduce waiting.

NotebookLM evidence: Google's [learning announcement](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-student-features/) and [notebook isolation](https://support.google.com/gemininotebook/answer/16206563?hl=en). The latter used Gemini Notebook as its title at review time; this report retains the familiar NotebookLM name.

LearnHouse evidence: [Trails](https://docs.learnhouse.app/platform/courses/trails), [AI context](https://docs.learnhouse.app/platform/ai), and [concepts](https://docs.learnhouse.app/getting-started/key-concepts). Collections organize cross-course paths without proving AI synthesis of dynamic prerequisite graphs.

## Selection judgment for these materials

1. No reviewed evidence establishes a complete solution to all three pain points. Define independent course state—concepts, prerequisites, pages, exercises, evidence, review items—rather than treating a long chat summary as state.
2. To minimize development, try a few original materials in RemNote and separately validate interface/review and cross-document fusion before migration.
3. Keep DeepTutor conditional on actual reading fixes and fusion tests. Use OpenMAIC as an interaction reference; multiple agents alone guarantee neither speed nor completeness.

## Short acceptance test

- Import all eight documents; produce concept—page—exercise coverage and randomly check 20 source points. Merely citing every file is insufficient.
- Check duplicate merging, prerequisites between related concepts, and exercises mapped to necessary knowledge.
- Deliberately answer a concept question incorrectly; check specific misconception records, remediation, and later review. Read status is not mastery.
- Reopen after interruption and verify the right concept, mistakes, pending exercises, and review after several days.
- Time first content, full lesson, and background note persistence separately; failed consolidation must not block teaching.

These tests distinguish documented features from suitability for long-term personal quantum learning.
