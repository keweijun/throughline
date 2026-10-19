# Domain Docs

## Layout

This project uses a single-domain layout: `GLOSSARY.md` at the root and `docs/adr/`. Separating generic teaching rules from course data does not make this a multi-domain repository.

## Usage

- Before exploring or changing the project, read `GLOSSARY.md` and the ADRs relevant to the task.
- If `GLOSSARY-MAP.md` exists in the future, follow its pointers to the relevant glossaries and ADRs.
- Continue if files are missing; create them through the domain-modeling workflow only when actual terminology or decisions emerge.
- Use glossary names in tasks, design, implementation, and validation; avoid explicitly excluded synonyms.
- Record and clarify real terminology gaps before updating the glossary.
- If a proposal conflicts with an existing ADR, identify the conflict and reason for reconsideration rather than silently rewriting the decision.
