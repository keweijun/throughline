import { t } from './i18n.svelte';
import { app } from './store.svelte';
import { zip } from './zip';
import type { Annotation, Chapter } from './types';

export type NoteGroup = { key: string; title: string; chapter?: Chapter; items: Annotation[] };

/**
 * Annotations by section, in route order, for the sections `ids`. Notes on a chapter recap or quiz question are grouped
 * with their chapter, after its last section, unless only one section is asked for; `empty` keeps sections without any.
 */
export function noteGroups(ids: string[], annotations: Annotation[], { single = false, empty = false } = {}): NoteGroup[] {
  const owner = new Map(annotations.map((a) => [a.id, app.ownerChapter(a)]));
  const result: NoteGroup[] = [];
  for (const id of ids) {
    const concept = app.concept(id);
    const home = app.chapterOf(id);
    if (!concept) continue;
    const items = annotations.filter((a) => a.concept_id === id && !owner.get(a.id));
    if (items.length || empty) result.push({ key: concept.id, title: concept.title, chapter: home, items });
    if (!single && home && home.concept_ids.at(-1) === id) {
      const chapterItems = annotations.filter((a) => owner.get(a.id) === home.id);
      if (chapterItems.length) result.push({ key: `chapter:${home.id}`, title: t('Chapter recap and quiz'), chapter: home, items: chapterItems });
    }
  }
  return result;
}

export function noteLabel(item: Annotation) {
  if (item.kind === 'note') return t('Section note');
  if (item.kind === 'bookmark') return t('Bookmark');
  // A highlight the learner wrote on reads as a note on that passage.
  return item.note ? t('Note') : t('Highlight');
}

/**
 * Every note in the course as a Markdown file, grouped by chapter and section, for keeping outside the app. Notes with
 * images come as a ZIP archive: the Markdown file and an images folder it links to.
 */
export async function exportNotes() {
  const groups = noteGroups(app.state?.curriculum.route ?? [], app.state?.annotations ?? []);
  const lines = [`# ${app.state?.course.title ?? ''}`];
  const pictures = new Set<string>();
  let heading: string | undefined;
  for (const group of groups) {
    if (group.chapter && group.chapter.title !== heading) lines.push('', `## ${(heading = group.chapter.title)}`);
    lines.push('', `${group.chapter ? '###' : '##'} ${group.title}`);
    for (const item of group.items) {
      lines.push('', `- ${noteLabel(item)}${item.source?.label ? ` (${item.source.label})` : ''}`);
      if (item.passage) lines.push(...item.passage.split('\n').map((line) => `  > ${line}`));
      if (item.note) lines.push(...item.note.split('\n').map((line) => `  ${line}`));
      for (const [i, image] of (item.images ?? []).entries()) {
        lines.push('', `  ![${t('Attached image {number}', { number: i + 1 })}](images/${image})`);
        pictures.add(image);
      }
    }
  }
  const name = (app.state?.course.title || 'notes').replace(/[\\/:*?"<>|]+/g, '-');
  const text = lines.join('\n') + '\n';
  let file: Blob = new Blob([text], { type: 'text/markdown' });
  if (pictures.size) {
    const files = [{ path: `${name}.md`, data: new TextEncoder().encode(text) }];
    for (const image of pictures) {
      const response = await fetch(`/api/images/${encodeURIComponent(image)}`).catch(() => null);
      if (response?.ok) files.push({ path: `images/${image}`, data: new Uint8Array(await response.arrayBuffer()) });
    }
    file = zip(files);
  }
  const link = document.createElement('a');
  link.href = URL.createObjectURL(file);
  link.download = `${name}.${pictures.size ? 'zip' : 'md'}`;
  link.click();
  // Revoking at once can cancel the download before the browser has read the file.
  setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
}
