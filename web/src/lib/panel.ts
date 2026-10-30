import { app } from './store.svelte';
import { t } from './i18n.svelte';
import type { Chapter } from './types';

/** Which part of the course a side-panel list shows; Questions and Notes offer the same three. */
export type PanelScope = 'section' | 'chapter' | 'all';

export type PanelGroup<T> = { key: string; title: string; chapter?: Chapter; items: T[] };

/**
 * Groups items by the section they belong to, in route order, for the sections the scope covers.
 * Items owned by a chapter (its recap or quiz) follow that chapter's last section; items whose
 * section is no longer on the route are kept in a last group rather than lost.
 */
export function groupBySection<T>(
  items: T[],
  scope: PanelScope,
  sectionOf: (item: T) => string | null | undefined,
  chapterOf: (item: T) => string | undefined = () => undefined,
): PanelGroup<T>[] {
  const viewing = app.viewingId;
  const chapter = app.chapterOf(viewing);
  const route = app.state?.curriculum.route ?? [];
  const ids = scope === 'section' ? [viewing] : scope === 'chapter' ? (chapter?.concept_ids ?? [viewing]) : route;
  const owned = new Map(items.map((item) => [item, chapterOf(item)]));
  const placed = new Set<T>();
  const groups: PanelGroup<T>[] = [];
  for (const id of ids) {
    const concept = app.concept(id);
    if (!concept) continue;
    const home = app.chapterOf(id);
    const own = items.filter((item) => !owned.get(item) && sectionOf(item) === id);
    if (own.length) groups.push({ key: concept.id, title: concept.title, chapter: home, items: own });
    if (scope !== 'section' && home && home.concept_ids.at(-1) === id) {
      const recap = items.filter((item) => owned.get(item) === home.id);
      if (recap.length) groups.push({ key: `chapter:${home.id}`, title: t("Chapter recap and quiz"), chapter: home, items: recap });
    }
  }
  for (const group of groups) for (const item of group.items) placed.add(item);
  if (scope === 'all') {
    const rest = items.filter((item) => !placed.has(item));
    if (rest.length) groups.push({ key: 'elsewhere', title: t("Elsewhere in the course"), items: rest });
  }
  return groups;
}

/** How many items each scope would show, for the counts on the scope selector. */
export function scopeCounts<T>(items: T[], sectionOf: (item: T) => string | null | undefined, chapterOf: (item: T) => string | undefined = () => undefined) {
  const count = (scope: PanelScope) => groupBySection(items, scope, sectionOf, chapterOf).reduce((n, g) => n + g.items.length, 0);
  return { section: count('section'), chapter: count('chapter'), all: items.length };
}
