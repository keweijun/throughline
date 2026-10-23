# The course workspace owns official learning state

Cross-document guided learning needs consistent learning evidence and mainline position across chat changes, source updates, and deferred consolidation. An independent course workspace is the sole official state; both the app and the Codex skill read and update it through the same operations (see ADR 0004 for the course library that holds the workspaces). Chat history is not the sole memory, and there is no Obsidian synchronization. The learner's own highlights, notes and bookmarks live in the course workspace as well, but are not teaching state (ADR 0005).

This choice favors explicit persistent records: a small amount of state maintenance and validation buys teaching continuity and prevents generic rule updates from affecting course data or multiple systems from overwriting progress.
