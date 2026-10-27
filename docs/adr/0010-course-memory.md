# The teacher keeps a course memory

Each lesson prompt carries the route, the section's sources, the learner profile, pending explanations and the last eight interactions. It does not carry what earlier lessons actually taught or what the learner said about how they want to be taught. In practice:

- A preference stated during practice ("one step at a time, no hints when I'm right"; "give me the tedious integrals") was followed in that exercise and then lost. The only lasting record was the learner profile, edited by hand in Codex.
- A later lesson could not tell that "plane wave" had already been explained in a side question, or that atomic units had not been taught yet, so it reused terms without defining them.
- Repeated difficulties (charge bookkeeping in Hamiltonians, independence of joint probabilities) appeared only as separate needs-work assessments.

We add a **course memory** to the course workspace (ADR 0001) with three kinds of entries:

- **Preferences**: how the learner wants to be taught, learned during teaching. Unlike the learner profile, which records what the learner reported when the course was built, these come from what they say or do later.
- **Taught terms**: a term or notation and the section, lesson step or side question where it was defined.
- **Difficulties**: an idea the learner has repeatedly got wrong, with the interactions that show it. A difficulty is cleared when a later check question or exercise on it is answered correctly.

Entries are facts about the learner and the course, each citing the interactions it came from. They never store phrasing, analogies or examples for the teacher to repeat. Issue #21 showed that analogies the learner raised anchor later lessons.

## Writing and reading

- At the end of each turn the teacher appends a structured memory note, as it already does with the side-question `<teaching-decision>` block. The host validates it and records it as operations. At the end of a section the small model merges duplicates and prunes cleared or stale entries.
- Check questions (ADR 0009) need no note: the host records a difficulty once two check answers on the same idea are missed, and clears it when a later check on the idea is answered correctly. Ideas match by their text, ignoring case, punctuation and spacing.
- A preference is saved only after the learner confirms it ("Remember: one step at a time?"). Taught terms and difficulties are saved directly. A preference suggested from repeated skip reasons (ADR 0011) cites the skipped exercises, since a skip has no interaction.
- The learner can see every entry and edit or delete it. Deleting is final: the teacher does not re-add an entry just because the same evidence still exists.
- Every lesson, side question, practice and preparation prompt includes the current memory. The teacher uses only taught terms without defining them; any other term gets a one-line definition or a bridge.

## Scope and boundaries

- Memory stays inside one course, including preferences. A new course starts empty.
- Memory is not learning evidence and never sets mastery; evidence operations are unchanged.
- Learner annotations remain private (ADR 0005). Memory is written by the teacher from teaching interactions and shown to the learner, not taken from their notes.
- The optional background study notes (`background.*`) are a different thing: consolidated notes about the material. They are not memory and do not enter app prompts.
