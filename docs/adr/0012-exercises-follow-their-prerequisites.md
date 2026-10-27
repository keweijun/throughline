# Exercises follow the concepts they need

Course exercises, especially homework, are mapped to route sections with the concepts they require. In one course 23 of 95 mappings placed an exercise before at least one of its required concepts, some by more than twenty sections. The lesson then had to teach whatever the exercise needed, which is how atomic units and a perturbation setup appeared in a lesson on operators.

An exercise part is mapped to the latest section among the concepts it requires, never earlier. A homework question whose parts need different concepts is split: each part goes to its own section, and keeps a reference to the original question and to where its other parts are taught. Curriculum validation rejects a mapping that comes before a required concept.

Deadlines do not override this. A learner who needs a homework part sooner can study the sections it needs, or ask for it as a side question.

Every exercise a save sends must list its `required_concepts`; without them the rule cannot be checked, and an optional field let exercises bypass it. Validation applies to what a save writes: the concepts it sends, and any violation it creates elsewhere by reordering or moving concepts. Courses mapped before this rule may hold violations; they keep opening and teaching, a read-only check (`curriculum.check`) lists them, and Codex fixes them one chapter at a time, since a chapter save does not fail on another chapter's earlier violations.
