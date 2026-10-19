# Codex Guided Learning

Personal cross-document guided learning using a Codex skill, an independent course workspace, and helper scripts. V1 prioritizes teaching continuity, material coverage, and route-aware question answering.

This branch is at the design and engineering-configuration stage; teaching functionality is not implemented here.

## Documents

- [V1 proposal](docs/v1-spec.md): teaching behavior, state boundaries, and acceptance scenarios.
- [Design interview](docs/design-interview.md): confirmed requirements and choices.
- [Domain glossary](GLOSSARY.md): shared project terminology.
- [Architecture decision](docs/adr/0001-course-workspace-owns-learning-state.md): the course workspace owns official learning state.
- [Earlier research](docs/research/): framework comparisons and workflow analysis; the V1 proposal supersedes historical suggestions.
- [Initial design archive](docs/archive/initial-design/): preserved early records.

The project lives at `F:\Projects\codex-guided-learning`. V1 is independent of Obsidian, with no compatibility, export, or synchronization integration.

Tasks use GitHub Issues. Start with [AGENTS.md](AGENTS.md) for engineering instructions and [docs/agents/](docs/agents/) for their rules; these configuration files can be edited directly.
