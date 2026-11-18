# Security

Throughline runs on the learner's own computer. It starts a local web host for the browser and drives Codex there. This page says what that host protects, and how to report a problem.

## Reporting a vulnerability

Please report it privately through GitHub's **Report a vulnerability** on the Security tab of this repository, not in a public issue. Say what an attacker can do, and include steps to reproduce it, plus the Throughline version (Settings → About) and your operating system. Fixes ship as a new release, and the one-click update in Settings → About installs it.

Only the latest release gets fixes.

## What the local host protects

- **Only this computer.** The host listens on `127.0.0.1` alone and refuses any request whose `Host` or `Origin` is not that address and port. That stops other computers and DNS-rebinding pages.
- **Only this browser tab, not other websites.** Requests from another site are refused (`Origin`, `Sec-Fetch-Site`). So are requests from Python cells, which run in a sandboxed frame with no origin.
- **Only this person on a shared computer.** Every API request needs the host key. It is kept in `<library>/.throughline/host-key`, which only the learner's account can read. The launcher and `guided-learning open` sign the browser in with an HttpOnly, SameSite=Strict cookie. Commands send the key in a header.
- **What Codex may do.** Studio works in the course library with Codex's sandbox, and asks before it writes anywhere else or reaches the network. Full access, with no sandbox and no approvals, only applies when the learner chooses it. That includes Windows computers where Codex's sandbox is not set up (ADR 0016).
- **Links Codex writes.** A link opens a document in its own app only when the document is of a type that runs nothing. Anything else, such as a script, an installer or a macOS app, is shown in the file manager instead.

## What it does not protect against

- Programs running as the same user. They can read the course library and the host key directly.
- Course packages from other people. Their documents and lessons reach Codex's prompts, so with Full access, text written to instruct Codex could change files. Studio warns about this on such courses.
- Mistakes in what the teacher model writes. Lessons and grading come from a model and can be wrong.
