## Language

Write documentation, agent instructions, comments, commit messages, pull requests and issues in English. The UI and generated teaching content default to English; learners may request another teaching language. Preserve the original language of imported sources and existing learning records.

## Domain

Read `GLOSSARY.md` and the relevant ADRs in `docs/adr/` before changing behavior, and use the glossary's terms. If a change conflicts with an ADR, say so and update the ADR rather than silently diverging. Architecture and the HTTP API are in `docs/architecture.md`.

## Working on the code

- Python tests: `.venv/bin/python -m unittest discover -s tests` (install with `pip install -e ".[pdf,dev]"`). Browser tests: `cd web && npx playwright test`.
- UI changes: run `npm run check` and `npm run build` in `web/`, and commit the rebuilt `guided_learning/web_dist`.
- The Codex skill lives in `guided_learning/skill/` and ships with the package; `guided-learning setup` installs it. Operation names and semantics in its references are a stable contract.
- A change that reshapes stored course data needs a migration in `guided_learning/migrations.py` and a test that starts from the old format (ADR 0007); learners have real courses.
- Never commit course materials or learning records; they belong in the course library or ignored `work/`.

## Versions

Learners are offered an update when the `version` in `pyproject.toml` on `main` is higher than theirs (Settings → About; ADR 0004), so a change merged without a bump never reaches them as an update. Every PR that changes what a learner installs bumps the version in the same PR:

- **Patch** (0.6.0 → 0.6.1): bug fixes and small interface polish.
- **Minor** (0.6.1 → 0.7.0): a new feature or a visible change in behavior, a migration of stored course data, or a change to the skill or its references.
- No bump for changes outside the installed package: tests, CI, the READMEs, ADRs and `docs/`.
- Major versions wait for 1.0.

Bump relative to `main` at merge time, not to where the branch started: if `main` has moved past your bump, bump again on top of it. State the new version in the PR description.

## Issues

Track tasks in this repository's GitHub Issues with `gh`. Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Close an issue only after recording the result and how it was verified.
