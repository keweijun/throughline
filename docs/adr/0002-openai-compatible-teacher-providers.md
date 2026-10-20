# The teacher can be any OpenAI-compatible model or the local Codex CLI

The v2 specification kept "automatic additional paid providers" out of scope and reused only the local Codex configuration. As the app became a standalone learning tool, learners needed to choose their own teacher model: hosted APIs, routers such as OpenRouter, or local servers such as Ollama and LM Studio.

The host now supports two runner kinds behind one interface, `run(prompt, cwd, emit, cancel)`: the existing Codex App Server runner, and a streaming client for the OpenAI chat completions API. Provider settings are stored per user (`~/.config/guided-learning/providers.json`, owner-only permissions), never inside a course workspace, so copying a course never copies keys. Keys are never returned to the browser. Local Codex remains the default.

What stays from the earlier decision: the app never switches or adds a provider automatically, and never retries on a different provider after a failure. The learner chooses explicitly in Model settings or with `--provider`/`--model` for one run. Changing provider affects new requests only; saved lessons and evidence keep their original text.

Prompts are identical for every provider, so teaching rules do not fork per model. Model quality still varies, and the program's checks (decision tags, practice JSON, evidence roles) remain the guard against malformed replies.
