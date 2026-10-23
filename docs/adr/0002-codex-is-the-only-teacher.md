# Codex is the only teacher

A course only exists after the Codex skill has prepared it: registering documents, extracting concepts, building the route and checking sources all happen in Codex. A learner of this app therefore always has a working Codex CLI and sign-in.

An earlier draft of this ADR let the interface use any OpenAI-compatible provider as the teacher. That added a provider registry, API key storage and a second model client without serving anyone who could not already run Codex, so it was removed. The host runs every lesson, side question, practice request and preparation through `codex app-server`. The learner chooses only the Codex model and reasoning effort, stored per user (`~/.config/guided-learning/settings.json`) and never in a course workspace; `--model` and `--effort` override them for one run.

The runner interface `run(prompt, cwd, emit, cancel, images=())` stays, because tests use fake runners through it; `images` carries rendered source pages for review (ADR 0004). Adding another model backend later would mean revisiting this decision, not just adding a class.
