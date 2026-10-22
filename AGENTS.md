## Language

Write documentation, agent instructions, comments, commit messages, pull requests and issues in English. The UI and generated teaching content default to English; learners may request another teaching language. Preserve the original language of imported sources and existing learning records.

## Domain

Read `GLOSSARY.md` and the relevant ADRs in `docs/adr/` before changing behavior, and use the glossary's terms. If a change conflicts with an ADR, say so and update the ADR rather than silently diverging. Architecture and the HTTP API are in `docs/architecture.md`.

## Working on the code

- Python tests: `.venv/bin/python -m unittest discover -s tests`. Browser tests: `cd web && npx playwright test`.
- UI changes: run `npm run check` and `npm run build` in `web/`, and commit the rebuilt `guided_learning/web_dist`.
- The Codex skill lives in `guided_learning/skill/` and ships with the package; `guided-learning setup` installs it. Operation names and semantics in its references are a stable contract.
- Never commit course materials or learning records; they belong in the course library or ignored `work/`.

## Issues

Track tasks in this repository's GitHub Issues with `gh`. Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Close an issue only after recording the result and how it was verified.
