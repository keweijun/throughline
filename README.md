# Codex Guided Learning

Personal cross-document guided learning: a Codex skill guides teacher behavior while a local course workspace preserves sources, routes, the teaching mainline, and actual learning evidence. V1 implements course operations, route-aware question answering, practice evidence, and recoverable Luna consolidation tasks. The teacher makes instructional judgments from the materials; the program validates state and references without automatically deciding whether a learner understands.

Project documentation is in English. Teaching defaults to English; learners can explicitly request another language. Imported materials and existing course records retain their original language.

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

## Current capabilities

- Register PDF/Markdown sources, retain revision snapshots and reading issues, and check source locations.
- Save cross-document concepts, prerequisite routes, notation, and exercise mappings; validate references, cycles, and coverage dispositions.
- Choose side-question depth using the current goal; resume after brief answers and wait after long answers. Follow-up questions within long branches can also link pending explanations.
- Group practice at section ends and keep taught, self-reported, hinted, independent, and retest evidence separate.
- Revisit deferred items when due; resume a new chat after a brief recap without a mandatory quiz.
- Keep the main teacher responsive. When the host provides Luna, it can consolidate candidate notes; otherwise tasks remain pending without automatic paid API calls.

An always-on service, dedicated learning UI, and public plugin distribution are outside V1. Session subagents are not services that continue after leaving chat.

## Prepared local quantum course

`work/courses/quantum-v1` registers six actual lecture documents and two exercise documents, totaling 231 pages, with 45 candidate concepts, 23 exercise subrequirements, and eight source-linked notation entries. Input copies are in `work/course-inputs/quantum`; runtime access does not depend on the original note application's directory.

**This is a candidate coverage map awaiting review.** Candidate mappings exist for 41 pages; 190 pages explicitly need review. Verification for all 231 pages remains pending. Only seven original PDF pages were spot-checked, which does not establish that all formulas, images, or concepts are verified. No personal old chats were imported and no artificial learning progress was created.

Course materials and the database stay in local `work/` and are not distributed with Git. Other machines must supply materials and create their own courses. [Course import and review](docs/course-import.md) explains local import replay and new-course creation. [V1 acceptance](docs/acceptance-v1.md) distinguishes program tests, real materials, teaching replay, and Luna checks.

## Design and development

- [V1 proposal](docs/v1-spec.md), [implementation specification](docs/implementation-spec.md), [task breakdown](docs/implementation-plan.md)
- [Design interview](docs/design-interview.md), [domain glossary](GLOSSARY.md), [state ownership ADR](docs/adr/0001-course-workspace-owns-learning-state.md)
- [Earlier research](docs/research/) retains historical comparisons; the V1 proposal defines the final V1 scope.

The project uses GitHub Issues; engineering instructions start at [AGENTS.md](AGENTS.md). It is independent of Obsidian, with no compatibility, export, or synchronization integration.
