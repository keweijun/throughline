import { t } from './i18n.svelte';
import { inMath, shownText } from './markdown';
import type { Ref, State } from './types';

/**
 * Search across the course (Shift Shift): section and chapter titles, lessons, side questions and their answers,
 * exercises with the learner's answers and the feedback on them, review questions and notes, all from the state the
 * interface already holds. Source text is not in the state; the host searches it (`/api/search/sources`).
 */

export type Group = 'sections' | 'lessons' | 'questions' | 'exercises' | 'notes' | 'sources';
export const GROUPS: Group[] = ['sections', 'lessons', 'questions', 'exercises', 'notes', 'sources'];

/** Where a hit leads. A passage names the matched words as they read, and which repeat of them, so the page can land on it. */
export type Target =
  | { kind: 'chapter'; id: string }
  | { kind: 'section'; id: string }
  | { kind: 'passage'; concept_id: string; turn_id: string | null; task_id?: string; passage: string; occurrence: number }
  | { kind: 'question'; id: string }
  | { kind: 'note'; id: string }
  | { kind: 'review'; task_id: string }
  | { kind: 'source'; ref: Ref };

/** Some text shown in a hit, with the matched stretches marked as [start, end) offsets. */
export type Snippet = { text: string; marks: [number, number][] };

export type Hit = { key: string; group: Group; title: string; context: string; snippet: Snippet; target: Target };

type Field = { text: string; lower: string };
type Item = {
  key: string;
  group: Group;
  title: string;
  context: string;
  /** Searched in order; the first holds the title, so a title that matches ranks first. */
  fields: Field[];
  /** The sections it belongs to, so the chapter the learner is in can rank first. */
  concepts: string[];
  /** Course order, or newest first, between hits that rank the same. */
  order: number;
  target: (field: Field, at: number, length: number) => Target;
};

const field = (text: string | null | undefined): Field => {
  const value = text ?? '';
  return { text: value, lower: value.toLowerCase() };
};

/** Markdown as it reads: without fences, tags, tables' rules, link targets, citation chips and block markers. Formulas
 * stay as TeX. */
export function plain(markdown: string) {
  return shownText(markdown)
    .replace(/^\s*```.*$/gm, ' ')
    .replace(/<\/?[a-z][^>]*>/gi, ' ')
    .replace(/^\s*\|?[\s:|-]*-{3,}[\s:|-]*\|?\s*$/gm, ' ')
    .replace(/^\s*\|(.*)\|\s*$/gm, (_, row: string) => row.replace(/\s\|\s/g, ' · '))
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[(?:Source|来源)\s+[^\]]*\]/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^\s{0,3}(?:#{1,6}|>|[-*+]|\d+[.)])\s+/gm, '')
    .replace(/\*\*|`/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Where a lesson or an exercise opens on a match: the matched words, unless they sit in a formula, and their repeat. */
function passage(concept_id: string, turn_id: string | null, task_id?: string) {
  return (f: Field, at: number, length: number): Target => {
    const words = f.text.slice(at, at + length);
    if (inMath(f.text, at)) return { kind: 'passage', concept_id, turn_id, task_id, passage: '', occurrence: 0 };
    let occurrence = 0;
    for (let i = f.text.indexOf(words); i >= 0 && i < at; i = f.text.indexOf(words, i + 1)) if (!inMath(f.text, i)) occurrence++;
    return { kind: 'passage', concept_id, turn_id, task_id, passage: words, occurrence };
  };
}

/** Everything searchable in a course, built once per state. */
export function index(state: State): Item[] {
  const concepts = new Map(state.curriculum.concepts.map((c) => [c.id, c]));
  const chapters = state.curriculum.chapters ?? [];
  const chapterOf = (conceptId: string) => chapters.find((c) => c.concept_ids.includes(conceptId));
  const route = state.curriculum.route;
  const place = (conceptId: string | null | undefined) => {
    const i = route.indexOf(conceptId ?? '');
    return i < 0 ? route.length : i;
  };
  const sectionTitle = (conceptId: string | null | undefined) => concepts.get(conceptId ?? '')?.title ?? '';
  const chapterTitle = (conceptId: string | null | undefined) => chapterOf(conceptId ?? '')?.title ?? '';
  const items: Item[] = [];

  chapters.forEach((chapter, i) => {
    items.push({ key: `chapter:${chapter.id}`, group: 'sections', title: chapter.title, context: t('Chapter {number}', { number: i + 1 }),
      fields: [field(chapter.title), field(chapter.summary)], concepts: chapter.concept_ids, order: place(chapter.concept_ids[0]) - 0.5, target: () => ({ kind: 'chapter', id: chapter.id }) });
  });
  for (const concept of state.curriculum.concepts) {
    if (!route.includes(concept.id)) continue;
    items.push({ key: `section:${concept.id}`, group: 'sections', title: concept.title, context: chapterTitle(concept.id),
      fields: [field(concept.title), field(concept.objective), field(concept.goal)], concepts: [concept.id], order: place(concept.id), target: () => ({ kind: 'section', id: concept.id }) });
  }

  const steps = new Map<string, { number: number; check?: string }>();
  for (const lesson of state.lessons) {
    lesson.steps.forEach((step, i) => {
      if (!step.turn_id) return;
      const check = step.check && [step.check.question, ...step.check.options.flatMap((o) => [o.text, o.explanation])].join(' ');
      steps.set(step.turn_id, { number: i + 1, check });
    });
  }
  for (const turn of state.turns) {
    if (turn.channel !== 'mainline' || !turn.text) continue;
    const step = steps.get(turn.id);
    const chapter = turn.chapter_id ? chapters.find((c) => c.id === turn.chapter_id) : undefined;
    const title = chapter ? `${chapter.title} · ${t('Chapter recap')}` : step ? `${sectionTitle(turn.concept_id)} · ${t('Step {number}', { number: step.number })}` : sectionTitle(turn.concept_id);
    items.push({ key: `lesson:${turn.id}`, group: 'lessons', title, context: chapter ? '' : chapterTitle(turn.concept_id),
      fields: [field(plain(turn.text)), field(step?.check)], concepts: chapter ? chapter.concept_ids : [turn.concept_id], order: place(turn.concept_id) + (step?.number ?? 0) / 100,
      target: passage(turn.concept_id, turn.id) });
  }

  const turns = new Map(state.turns.map((turn) => [turn.id, turn]));
  const answer = (id: string | null | undefined) => field(plain(turns.get(id ?? '')?.text ?? ''));
  for (const question of state.questions) {
    const replies = question.replies ?? [];
    const section = question.anchor?.concept_id ?? question.restore_point?.concept_id;
    items.push({ key: `question:${question.id}`, group: 'questions', title: question.question, context: sectionTitle(section),
      fields: [field(question.question), answer(question.turn_id), answer(question.supplement_turn_id), ...replies.flatMap((r) => [field(r.question), answer(r.turn_id)])],
      concepts: section ? [section] : [], order: -(question.created_at ?? 0), target: () => ({ kind: 'question', id: question.id }) });
  }

  for (const task of [...state.practice.tasks, ...state.review.tasks]) {
    const review = task.origin === 'review';
    const parts = (task.parts ?? []).map((p) => (typeof p === 'string' ? p : p.text));
    const history = task.history.flatMap((h) => [h.answer, h.question, h.feedback].map((text) => field(plain(text ?? ''))));
    const label = review ? t('Review question') : task.origin === 'chapter_quiz' ? t('Quiz question') : t('Exercise');
    items.push({ key: `task:${task.id}`, group: 'exercises', title: `${label} · ${task.chapter_id ? (chapters.find((c) => c.id === task.chapter_id)?.title ?? '') : sectionTitle(task.concept_id)}`,
      context: '', fields: [field(plain(task.question)), ...parts.map((p) => field(plain(p))), ...history],
      concepts: task.tests_concept_ids?.length ? task.tests_concept_ids : [task.concept_id], order: review ? route.length + 1 - (task.created_at ?? 0) / 1e12 : place(task.concept_id) + (task.created_at ?? 0) / 1e12,
      target: review ? () => ({ kind: 'review', task_id: task.id }) : passage(task.concept_id, null, task.id) });
  }

  for (const note of state.annotations) {
    if (note.kind !== 'note') continue;
    items.push({ key: `note:${note.id}`, group: 'notes', title: note.note.split('\n')[0] || note.passage, context: sectionTitle(note.concept_id),
      fields: [field(note.note), field(note.passage)], concepts: [note.concept_id], order: -note.updated_at, target: () => ({ kind: 'note', id: note.id }) });
  }
  return items;
}

/** The words of a query, each to be found somewhere in an item. */
export const terms = (query: string) => query.toLowerCase().split(/\s+/).filter(Boolean);

/** Some text around a match, cut near word boundaries, with every term in it marked. */
export function snippet(text: string, at: number, words: string[], before = 40, after = 140): Snippet {
  let start = Math.max(0, at - before);
  let end = Math.min(text.length, at + (words[0]?.length ?? 0) + after);
  if (start > 0) {
    const space = text.indexOf(' ', start);
    if (space >= 0 && space < at) start = space + 1;
  }
  if (end < text.length) {
    const space = text.lastIndexOf(' ', end);
    if (space > at) end = space;
  }
  const lead = start > 0 ? '…' : '';
  const shown = lead + text.slice(start, end) + (end < text.length ? '…' : '');
  const lower = shown.toLowerCase();
  const marks: [number, number][] = [];
  for (const word of words) for (let i = lower.indexOf(word); i >= 0; i = lower.indexOf(word, i + word.length)) marks.push([i, i + word.length]);
  marks.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const mark of marks) {
    const last = merged[merged.length - 1];
    // Words matched side by side read as one match.
    if (last && (mark[0] <= last[1] || !shown.slice(last[1], mark[0]).trim())) last[1] = Math.max(last[1], mark[1]);
    else merged.push([...mark]);
  }
  return { text: shown, marks: merged };
}

/** How many times a word occurs in a text. */
function occurrences(text: string, word: string) {
  let count = 0;
  for (let i = text.indexOf(word); i >= 0; i = text.indexOf(word, i + word.length)) count++;
  return count;
}

/**
 * The items holding every word of the query, best first within each group: those whose title (a question's own text,
 * an exercise's question) holds every word, then by score, then in course order. The score grows with how often the
 * words occur, slowly, so a long lesson does not win on length alone, and by one for items in `near`, the sections of
 * the chapter the learner is in: about what doubling the mentions earns.
 */
export function search(items: Item[], query: string, near: ReadonlySet<string> = new Set()): Hit[] {
  const words = terms(query);
  if (!words.length) return [];
  const hits: (Hit & { rank: number; score: number; order: number })[] = [];
  for (const item of items) {
    if (!words.every((w) => item.fields.some((f) => f.lower.includes(w)))) continue;
    const mentions = item.fields.reduce((sum, f) => sum + words.reduce((n, w) => n + occurrences(f.lower, w), 0), 0);
    const score = Math.log2(1 + mentions) + (item.concepts.some((c) => near.has(c)) ? 1 : 0);
    const first = item.fields.find((f) => f.lower.includes(words[0]))!;
    // The page lands on the whole query where it reads as a phrase, else on its first word.
    const phrase = words.join(' ');
    const whole = words.length > 1 ? item.fields.find((f) => f.lower.includes(phrase)) : undefined;
    const at = whole ? whole.lower.indexOf(phrase) : first.lower.indexOf(words[0]);
    const titled = words.every((w) => item.fields[0].lower.includes(w));
    // A title that matches is the hit itself; its snippet shows the description, when there is one.
    const found = whole ?? first;
    const shown = titled && item.group === 'sections' ? (item.fields.find((f, i) => i > 0 && f.text) ?? found) : found;
    hits.push({
      key: item.key, group: item.group, title: item.title, context: item.context,
      snippet: shown === found ? snippet(found.text, at, words) : snippet(shown.text, 0, words),
      target: item.target(found, at, whole ? phrase.length : words[0].length), rank: titled ? 0 : 1, score, order: item.order,
    });
  }
  return hits.sort((a, b) => GROUPS.indexOf(a.group) - GROUPS.indexOf(b.group) || a.rank - b.rank || b.score - a.score || a.order - b.order)
    .map(({ rank, score, order, ...hit }) => hit);
}

/** A source page the host found, as a hit. */
export function sourceHit(unit: Ref & { path: string; excerpt: string }, query: string, label: string): Hit {
  const name = unit.path.split(/[\\/]/).pop() ?? unit.path;
  const words = terms(query);
  const lower = unit.excerpt.toLowerCase();
  return { key: `source:${unit.source_id}:${unit.unit_id}`, group: 'sources', title: `${name} · ${label}`, context: '',
    snippet: snippet(unit.excerpt, Math.max(0, lower.indexOf(words[0] ?? '')), words, 1e6, 1e6),
    target: { kind: 'source', ref: { source_id: unit.source_id, revision: unit.revision, unit_id: unit.unit_id } } };
}
