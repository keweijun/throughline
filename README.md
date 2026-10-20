# Codex Guided Learning

Personal cross-document guided learning: a Codex skill guides teacher behavior while a local course workspace preserves sources, routes, the teaching mainline, and actual learning evidence. A local learning interface provides streaming lessons, unit overviews, original source pages, side questions, practice, and next-section preparation. The teacher makes instructional judgments from the materials; the program validates state and references without automatically deciding whether a learner understands.

Project documentation is in English. The UI supports English and Simplified Chinese, with English as the default. The header's language selector controls the interface and new teaching content, including side answers, exercises, hints, and feedback. The choice is saved in the course workspace. Imported materials and existing course records retain their original language.

## Install and invoke

Requires Python 3.10+. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[pdf]'
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Open this project in Codex and invoke `$guided-learning`. The repository skill is at [.agents/skills/guided-learning/SKILL.md](.agents/skills/guided-learning/SKILL.md). If the current chat has not discovered it, start a new project chat or explicitly ask Codex to read that file. The skill is separate from individual course state and need not be copied into the global skills directory.

For example:

> Use guided-learning to open work/courses/quantum-v1 in this project. Briefly explain the candidate route and material still awaiting verification, then begin guided learning from wavefunctions. Do not count demonstrations or self-reported understanding as independent completion.

The operation entrypoint accepts JSON from a UTF-8 request file or standard input:

```powershell
'{"op":"course.init","title":"My course"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/demo
'{"op":"position.save","request_id":"demo-checkpoint-1","position":{"goal":"Prepare course","next_step":"Register materials"}}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/demo
'{"op":"session.resume"}' | .\.venv\Scripts\python.exe -m guided_learning --workspace work/courses/demo
```

Position-changing operations `position.save` and `mainline.enter` require a unique `request_id`. Reuse the same ID for retries; an old request cannot overwrite newer progress. Use `interaction.read {id}` to inspect original exchanges beyond the recent-history window.

Success returns `{ok:true,result:...}`; failure returns `{ok:false,error:...}` and a nonzero exit code. `--request` takes a JSON **file path**. Use `--request work/request.json` to avoid shell escaping for complex formulas or long text.

## Open the V2 learning interface

Complete the installation above and make sure the current terminal can run `codex` with a configured model provider. The host reuses local Codex configuration; it does not store another API key or automatically choose a new paid provider. From the project root:

```powershell
.\.venv\Scripts\python.exe -m guided_learning.web --workspace work/courses/quantum-v1 --port 8765 --model gpt-6.1-sol --effort medium
```

Open [the local learning interface](http://127.0.0.1:8765). The course must already exist. On another machine, first follow [course import](docs/course-import.md) to create a course and replace `--workspace`. The model must be supported by your configured provider; omit `--model` to use its default. The course path is distinct from the original PDF directory.

Keep the terminal running; press Ctrl+C to stop. Repeat the command to resume the same course. UI actions save to that course. To try a copy, stop the host, copy the entire course directory, and use the copy's path. [Usage and recovery](docs/learning-ui.md) covers pause, branches, practice, and troubleshooting; [V2 acceptance](docs/acceptance-v2.md) separates automated tests, real-model checks, and teaching checks.

Markdown, math rendering, and fonts are bundled without runtime CDN access. Model generation still needs a network connection and valid local Codex configuration. Original PDF page rendering requires `.[pdf]`.

## Current capabilities

- Register PDF/Markdown sources, retain revision snapshots and reading issues, and check source locations.
- Save cross-document concepts, prerequisite routes, notation, and exercise mappings; validate references, cycles, and coverage dispositions.
- Choose side-question depth using the current goal; resume after brief answers and wait after long answers. Follow-up questions within long branches can also link pending explanations.
- Group practice at section ends and keep taught, self-reported, hinted, independent, and retest evidence separate.
- Revisit deferred items when due; resume a new chat after a brief recap without a mandatory quiz.
- Keep the main teacher responsive. When the host provides Luna, it can consolidate candidate notes; otherwise tasks remain pending without automatic paid API calls.

Background preparation runs only while the local learning host is running. It does not persist as a service after shutdown. Public plugin distribution is outside the current scope.

### V2 original-page dependencies

The interface uses pypdfium2 and Pillow from the `pdf` extra to render the exact registered PDF revision as an image, independently of browser PDF plugins. Update with `.\.venv\Scripts\python.exe -m pip install -e ".[pdf]"`. Without the renderer, the UI explicitly reports that the image is unavailable and still links to the original PDF.

## Prepared local quantum course

`work/courses/quantum-v1` registers six actual lecture documents and two exercise documents, totaling 231 pages, with 45 candidate concepts, 23 exercise subrequirements, and eight source-linked notation entries. Input copies are in `work/course-inputs/quantum`; runtime access does not depend on the original note application's directory.

**This is a candidate coverage map awaiting review.** Candidate mappings exist for 41 pages; 190 pages explicitly need review. Verification for all 231 pages remains pending. Only seven original PDF pages were spot-checked, which does not establish that all formulas, images, or concepts are verified. No personal old chats were imported and no artificial learning progress was created.

Course materials and the database stay in local `work/` and are not distributed with Git. Other machines must supply materials and create their own courses. [Course import and review](docs/course-import.md) explains local import replay and new-course creation. [V1 acceptance](docs/acceptance-v1.md) distinguishes program tests, real materials, teaching replay, and Luna checks.

## Design and development

- [V1 proposal](docs/v1-spec.md), [implementation specification](docs/implementation-spec.md), [task breakdown](docs/implementation-plan.md)
- [Design interview](docs/design-interview.md), [domain glossary](GLOSSARY.md), [state ownership ADR](docs/adr/0001-course-workspace-owns-learning-state.md)
- [Earlier research](docs/research/) retains historical comparisons; the V1 proposal defines the final V1 scope.

The project uses GitHub Issues; engineering instructions start at [AGENTS.md](AGENTS.md). It is independent of Obsidian, with no compatibility, export, or synchronization integration.
