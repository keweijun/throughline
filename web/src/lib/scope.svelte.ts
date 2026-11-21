import { app } from './store.svelte';

/** What the Review place covers (issue #219): chosen chapters and sections, or, with neither, everything studied. */
export type ReviewScope = { chapter_ids: string[]; concept_ids: string[] };

const EMPTY: ReviewScope = { chapter_ids: [], concept_ids: [] };
const key = () => `review-scope:${app.state?.course.id ?? ''}`;

/** The scope the learner last chose in this course, kept in this browser; a stored one that names nothing is ignored. */
export function storedScope(): ReviewScope {
  try {
    const value = JSON.parse(localStorage.getItem(key()) ?? 'null');
    if (value && Array.isArray(value.chapter_ids) && Array.isArray(value.concept_ids)) return value;
  } catch {
    // Storage may be unavailable; everything studied is the scope then.
  }
  return EMPTY;
}

export function storeScope(value: ReviewScope) {
  try {
    if (!value.chapter_ids.length && !value.concept_ids.length) localStorage.removeItem(key());
    else localStorage.setItem(key(), JSON.stringify(value));
  } catch {
    // Remembering the scope is a convenience.
  }
}

/** Whether a section can be reviewed: it has a lesson, key points or practice of its own (ADR 0014). */
export function reviewable(id: string) {
  return !!app.state?.review.sections?.includes(id) || app.studied(id) || !!app.keyPoints(id);
}

/** The studied sections a scope covers, in route order: all of them when it names none. */
export function scopeSections(value: ReviewScope): string[] {
  const studied = (app.state?.curriculum.route ?? []).filter(reviewable);
  if (!value.chapter_ids.length && !value.concept_ids.length) return studied;
  const chosen = new Set([
    ...value.concept_ids,
    ...app.chapters.filter((c) => value.chapter_ids.includes(c.id)).flatMap((c) => c.concept_ids),
  ]);
  return studied.filter((id) => chosen.has(id));
}
