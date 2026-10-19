# Issue tracker: GitHub

Use GitHub Issues for tasks and implementation specifications, operated through `gh`. Confirm repository identity with `git remote -v`; run commands from this project directory.

## Operations

- Create a task: `gh issue create --title "Title" --body-file <body-file>`.
- Read a task and discussion: `gh issue view <number> --comments`.
- Query tasks: `gh issue list --state open --json number,title,body,labels`, adding label filters as needed.
- Add discussion: `gh issue comment <number> --body-file <body-file>`.
- Update labels: `gh issue edit <number> --add-label <label>` or `--remove-label <label>`.
- Complete a task: record results and validation evidence, then run `gh issue close <number>`.
- Write multiline bodies to UTF-8 temporary files under ignored `work/` and pass them with `--body-file`.
- When a skill requires publishing a specification or task, create a GitHub Issue; when it requires retrieving a task, read the corresponding issue and comments.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Wayfinding

- A Map is a parent issue labeled `wayfinder:map`; link tasks as GitHub sub-issues. If unavailable, keep a task list in the parent and write `Part of #<number>` in each child.
- Use `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task` for child task types.
- Prefer native GitHub issue dependencies; otherwise record `Blocked by: #<number>` in the body.
- The Frontier consists of open, unassigned child tasks with no unfinished blockers, processed in the parent's order.
- Assign a claimed task to its actual executor. On resolution, append results, close the child, and update decisions and links in the parent.
- Check current CLI support and permissions when first using these optional features.
