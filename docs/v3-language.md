# Language selection in V3

The V2 language feature from `fa3360a` (#17) is now ported to the FastAPI host and Svelte interface. Its original commit is merged into the V3 history; legacy HTTP and DOM modules are not reintroduced.

One visible selector chooses English (default) or Simplified Chinese for the interface and new teaching requests. The course owns the preference. Reloads and host restarts preserve it; changing it does not discard drafts, translate imported sources or old replies, move the mainline, or create mastery evidence.

Each running attempt keeps its original language. Regeneration uses the current selection while preserving the previous attempt's metadata. Lessons, side questions, supplements, practice and preparation share the same teacher-language boundary. JSON keys/enumerations and citation markers remain stable. A language change invalidates preparation from the previous language; a failed task in one language does not block preparing in the other.

## Validation

- 90 Python tests passed, including course preference persistence, invalid values, frozen requests/retries, regeneration, HTTP selection, and language-sensitive preparation.
- Svelte check: zero errors and warnings. Production assets rebuilt and committed.
- 15 Playwright tests passed after final fixes, including all existing V3 flows and four bilingual scenarios covering drafts, original records, mobile selection, reloads, running-turn language, practice and translated fallback labels.
- Two real Codex CLI calls on an isolated synthetic course used the same neutral question. `zh-CN` returned a Chinese definition of probability amplitude; `en` returned the corresponding English definition. Both completed. This verifies the selected-language prompt path in one example, not universal model compliance. Raw results remain under the main project's ignored `work/v3-trial/language-smoke-results.json`.

## Standards

Independent review found no hard-rule or actionable maintainability findings. Course state ownership, English defaults, source/history preservation, and centralized teacher instructions are retained.

## Spec

Independent review found two untranslated fallback labels (default Codex effort and a missing source location). Both now use existing translations, with browser regression assertions and a focused follow-up review. No open specification findings remain.
