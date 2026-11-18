## Language

Write documentation, agent instructions, comments, commit messages, pull requests and issues in English. The UI and generated teaching content default to English; learners may request another teaching language. Preserve the original language of imported sources and existing learning records.

## Domain

Read `GLOSSARY.md` and the relevant ADRs in `docs/adr/` before changing behavior, and use the glossary's terms. If a change conflicts with an ADR, say so and update the ADR rather than silently diverging. Architecture and the HTTP API are in `docs/architecture.md`.

## Working on the code

- Python tests: `.venv/bin/python -m unittest discover -s tests` (install with `pip install -e ".[pdf,dev]"`). Browser tests: `cd web && npx playwright test`.
- UI changes: run `npm run check` and `npm run build` in `web/`, and commit the rebuilt `guided_learning/web_dist`.
- A PR that changes what learners see shows before/after screenshots in its description. Take both with one throwaway Playwright spec (same fixture, viewport and steps), first against `origin/main`'s build and then against the branch's, and don't commit the spec or its fixture. Make them look like a learner's real screen: a throwaway fixture with plausible course content and finished answers, never test placeholders, failed or streaming states, or first-visit tips; `deviceScaleFactor: 2`; and crop to the part that changed (a panel, not the whole window) unless the change is about where the page goes. Put the PNGs under `<branch-name>/` on the orphan `pr-screenshots` branch, never on the PR's branch, and embed them from `https://raw.githubusercontent.com/keweijun/throughline/pr-screenshots/<branch-name>/<file>.png`.
- The Codex skill lives in `guided_learning/skill/` and ships with the package; `guided-learning setup` installs it. Operation names and semantics in its references are a stable contract (`docs/stability.md`), as are course and package formats, the commands, and per-user files keeping keys they don't know.
- A change that reshapes stored course data needs a migration in `guided_learning/migrations.py` and a test that starts from the old format (ADR 0007); learners have real courses. A change that adds a migration also generates the fixture for the new format with `.venv/bin/python -m tests.fixtures.make_course`, which `tests/test_course_fixtures.py` opens with every later version.
- Never commit course materials or learning records; they belong in the course library or ignored `work/`.

## Versions

Learners install the latest release, and are offered an update when its version is higher than theirs (Settings → About; ADR 0021). A release is a version bump merged to `main`: once CI passes, it tags `v<version>`, publishes a GitHub release and moves the `stable` branch that installs fetch. A change merged without a bump never reaches learners. Every PR that changes what a learner installs bumps the version in the same PR and adds a `## <version>` entry to `CHANGELOG.md`, written for learners; CI fails the PR otherwise (`scripts/release.py check`):

- **Patch** (0.6.0 → 0.6.1): bug fixes and small interface polish.
- **Minor** (0.6.1 → 0.7.0): a new feature or a visible change in behavior, a migration of stored course data, or a change to the skill or its references.
- No bump for changes outside the installed package: tests, CI, the READMEs, ADRs and `docs/`.
- **Major** (1.x → 2.0): breaking anything `docs/stability.md` promises. Before 1.0, nothing is a major change.

Bump relative to `main` at merge time, not to where the branch started: if `main` has moved past your bump, bump again on top of it and rename your changelog entry, folding it into any entry already there for that version. State the new version in the PR description.

## Issues

Track tasks in this repository's GitHub Issues with `gh`. Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Close an issue only after recording the result and how it was verified.
