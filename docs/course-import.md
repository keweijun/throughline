# Creating and reviewing a course

Ask Codex `$throughline create a course called <name> from these files: …`. The skill follows the steps below; they are written out here so the result can be checked or reproduced by hand with the `guided-learning` command.

1. **Collect sources.** Copy the originals into `<library>/<name>/inputs/`, keeping the originals elsewhere. Source identity follows the absolute path, so register stable copies, not files in Downloads or a temporary folder. `guided-learning courses` prints the library root.
2. **Register.** Run `course.init`, `course.profile.save` with the learner's interview answers, `preferences.save` with the teaching language if it is not English, then `source.register {path}` for each copy, and inspect each with `source.read {source_id}`. Reading success only establishes text extraction: PDFs are split by physical page (`page-1` onward), Markdown by line, and the two locators are never mixed.
3. **Outline chapters.** Show the learner the chapter outline, then save it with `curriculum.outline`. See [course operations](../guided_learning/skill/references/course-operations.md) and [curriculum operations](../guided_learning/skill/references/curriculum.md).
4. **Build each chapter.** For each chapter in order, `curriculum.chapter.save` its sections (each with a `core_question` and `objective`) and the coverage of its source units, using the returned `source_id`, `revision` and `unit_id` for every link. Missing images, unclear formulas, failed extraction or undecided meaning become `needs_review` with a reason. Keep dispositions for in-scope content that is deferred, even if no exercise tests it. Keep each UTF-8 JSON request so it can be replayed with `--request`.
5. **Check and open.** Inspect all units and `semantic_completeness` in `curriculum.coverage`, and open the course in the app after the first chapter. Importing a route never creates taught or mastered records; the app records lessons, questions and practice once the learner studies.

## Reviewing

The library shows how many source locations are not checked yet. Ask Codex to `review the pages that still need review in <name>`; review upcoming pages first. Submit `verification: verified` with a substantive `verification_note` only after the check was actually done. Source verification, taught content and independent answering are separate records.

## Replaying and changing an import

Keep each request as one JSON line in an `import-requests.jsonl` file next to the course to reproduce it:

```sh
while IFS= read -r line; do
  printf '%s' "$line" | guided-learning --workspace path/to/replay-course || break
done < import-requests.jsonl
```

A replay reproduces the import only while the registered copies stay where they were and unchanged; normalized paths determine source IDs and content changes create new revisions. On another computer, register again and rebuild links from the returned IDs and revisions.

After real learning has started, do not overwrite the active route with a fresh candidate import. Review it in a new course first, confirm any major reordering, and keep concept IDs and evidence stable.
