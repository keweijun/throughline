<script lang="ts">
  import { enterToSend } from '../lib/keys';
  import PanelComposer from './PanelComposer.svelte';
  import { slide } from 'svelte/transition';
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { autogrow } from '../lib/autogrow';
  import type { Annotation, Chapter } from '../lib/types';

  let scope = $state<'section' | 'chapter' | 'all'>('section');
  let search = $state('');
  let editing = $state<string | null>(null);
  let edit = $state('');
  let flash = $state<string | null>(null);

  const viewing = $derived(app.viewingId);
  // The note draft is kept per section, like the other writing boxes, so it survives a look elsewhere.
  const draftKey = $derived(`note:${viewing}`);
  const draft = $derived(app.drafts.get(draftKey));
  const words = $derived(search.toLowerCase().split(/\s+/).filter(Boolean));
  const matches = (a: Annotation) => words.every((w) => [a.passage, a.note, a.source?.label ?? ''].join(' ').toLowerCase().includes(w));
  const chapter = $derived(app.chapterOf(viewing));
  // Notes on a chapter recap or quiz question are grouped with their chapter, after its sections, not in the anchor section.
  const groups = $derived.by(() => {
    const all = (app.state?.annotations ?? []).filter(matches);
    const owner = new Map(all.map((a) => [a.id, app.ownerChapter(a)]));
    const route = app.state?.curriculum.route ?? [];
    const ids = scope === 'section' ? [viewing] : scope === 'chapter' ? (chapter?.concept_ids ?? []) : route;
    const result: { key: string; title: string; chapter?: Chapter; items: Annotation[] }[] = [];
    for (const id of ids) {
      const concept = app.concept(id);
      const home = app.chapterOf(id);
      if (!concept) continue;
      const items = all.filter((a) => a.concept_id === id && !owner.get(a.id));
      if (items.length || (scope === 'section' && !words.length)) result.push({ key: concept.id, title: concept.title, chapter: home, items });
      if (scope !== 'section' && home && home.concept_ids.at(-1) === id) {
        const chapterItems = all.filter((a) => owner.get(a.id) === home.id);
        if (chapterItems.length) result.push({ key: `chapter:${home.id}`, title: t("Chapter recap and quiz"), chapter: home, items: chapterItems });
      }
    }
    return result;
  });
  const shown = $derived(groups.reduce((n, g) => n + g.items.length, 0));

  // A section outside any chapter has no "This chapter" choice; fall back rather than show nothing.
  $effect(() => {
    if (scope === 'chapter' && !chapter) scope = 'section';
  });


  /** Your notes as a Markdown file, grouped by chapter and section, for keeping outside the app. */
  function exportNotes() {
    const lines = [`# ${app.state?.course.title ?? ''}`];
    let heading: string | undefined;
    for (const group of groups) {
      if (group.chapter && group.chapter.title !== heading) lines.push('', `## ${(heading = group.chapter.title)}`);
      lines.push('', `${group.chapter ? '###' : '##'} ${group.title}`);
      for (const item of group.items) {
        lines.push('', `- ${label(item)}${item.source?.label ? ` (${item.source.label})` : ''}`);
        if (item.passage) lines.push(...item.passage.split('\n').map((line) => `  > ${line}`));
        if (item.note) lines.push(...item.note.split('\n').map((line) => `  ${line}`));
      }
    }
    const name = scope === 'chapter' ? chapter?.title : scope === 'section' ? groups[0]?.title : app.state?.course.title;
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([lines.join('\n') + '\n'], { type: 'text/markdown' }));
    link.download = `${(name ?? 'notes').replace(/[\\/:*?"<>|]+/g, '-')}.md`;
    link.click();
    // Revoking at once can cancel the download before the browser has read the file.
    setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
  }
  const total = $derived(app.state?.annotations.length ?? 0);

  async function add() {
    const section = viewing;
    const text = draft;
    const key = draftKey;
    if (!section || !text.trim()) return;
    if (!(await app.annotate({ kind: 'note', concept_id: section, note: text }))) return;
    if (app.drafts.get(key) === text) app.drafts.set(key, '');
    // The new note may land mid-list when several sections are shown; bring it into view.
    const added = [...(app.state?.annotations ?? [])].reverse().find((a) => a.kind === 'note' && a.concept_id === section && a.note === text);
    if (added) app.focusAnnotation = added.id;
  }

  function start(item: Annotation) {
    editing = item.id;
    edit = item.note;
  }

  async function saveEdit(item: Annotation) {
    if (item.kind === 'note' && !edit.trim()) return;
    if (await app.editNote(item.id, edit)) editing = null;
  }

  function remove(item: Annotation) {
    if (item.note && !confirm(t("Delete this note?"))) return;
    void app.removeAnnotation(item.id);
  }

  function label(item: Annotation) {
    if (item.kind === 'note') return t("Section note");
    if (item.kind === 'bookmark') return t("Bookmark");
    // A highlight the learner wrote on reads as a note on that passage.
    return item.note ? t("Note") : t("Highlight");
  }

  $effect(() => {
    const id = app.focusAnnotation;
    if (!id || !app.panelOpen || app.panelTab !== 'notes') return;
    const item = app.state?.annotations.find((a) => a.id === id);
    if (item && !matches(item)) search = '';
    if (item && (item.concept_id !== viewing || app.ownerChapter(item))) scope = 'all';
    app.focusAnnotation = null;
    flash = id;
    requestAnimationFrame(() => document.getElementById(`annotation-${id}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' }));
    const timer = setTimeout(() => (flash = null), 1600);
    return () => clearTimeout(timer);
  });
</script>

<section class="notes-panel panel-view" aria-labelledby="notes-title">
  <header class="panel-head">
    <div class="panel-bar">
      <h2 id="notes-title">{t("Your notes")}</h2>
      <div class="segmented" role="radiogroup" aria-label={t("Show notes from")}>
        <label><input type="radio" bind:group={scope} value="section" />{t("This section")}</label>
        {#if chapter}<label><input type="radio" bind:group={scope} value="chapter" />{t("This chapter")}</label>{/if}
        <label><input type="radio" bind:group={scope} value="all" />{t("All sections ({count})", { count: total })}</label>
      </div>
    </div>
    <p class="panel-intro">{t("Select text in a lesson or source to highlight it or add a note. Only you see these; the teacher does not.")}</p>
    {#if total > 4 || shown}
      <div class="panel-tools">
        {#if total > 4}<input type="search" bind:value={search} aria-label={t("Search notes")} placeholder={t("Search your notes…")} />{/if}
        {#if shown}<button class="btn btn-quiet btn-small export" class:btn-flush={total <= 4} onclick={exportNotes}>{t("Export as Markdown")}</button>{/if}
      </div>
    {/if}
  </header>

  <div class="panel-list">
  {#each groups as group, i (group.key)}
    {#if scope === 'all' && group.chapter && group.chapter.id !== groups[i - 1]?.chapter?.id}
      <h3 class="chapter">{group.chapter.title}</h3>
    {/if}
    <section class="group">
      <h3>{group.title}</h3>
      {#if !group.items.length}
        <p class="panel-empty">{t("Nothing saved for this section yet.")}</p>
      {/if}
      <ul>
        {#each group.items as item (item.id)}
          <li id="annotation-{item.id}" class="item {item.kind}" class:flash={flash === item.id} transition:slide={{ duration: 200 }}>
            <p class="kind">
              {label(item)}{#if item.source?.label}<span class="where"> · {item.source.label}</span>{:else if item.task_id}<span class="where"> · {t("Exercise")}</span>{:else if app.turn(item.turn_id)?.channel === 'sidequestion'}<span class="where"> · {t("Answer to a side question")}</span>{/if}
            </p>
            {#if item.passage}
              <blockquote class="prose" use:markdown={{ language: locale.language, text: item.passage }}></blockquote>
            {/if}
            {#if editing === item.id}
              <textarea
                rows="3"
                bind:value={edit} use:autogrow={edit}
                aria-label={t("Note")}
                use:enterToSend={() => void saveEdit(item)}
                onkeydown={(e) => e.key === 'Escape' && (editing = null)}
              ></textarea>
              <div class="actions">
                <button class="btn btn-quiet btn-small" onclick={() => (editing = null)}>{t("Cancel")}</button>
                <button class="btn btn-small" onclick={() => saveEdit(item)}>{t("Save")}</button>
              </div>
            {:else}
              {#if item.note}<p class="text">{item.note}</p>{/if}
              <div class="actions">
                {#if item.kind !== 'note'}
                  <button class="btn btn-quiet btn-small" onclick={() => app.goTo(item)}>{t("Go to")}</button>
                {/if}
                <button class="btn btn-quiet btn-small" onclick={() => start(item)}>{item.note ? t("Edit") : t("Add note")}</button>
                <button class="btn btn-quiet btn-small" onclick={() => remove(item)}>{t("Delete")}</button>
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {:else}
    <p class="panel-empty">{words.length ? t("No notes match your search.") : t("No highlights, notes or bookmarks yet.")}</p>
  {/each}
  </div>

  {#if viewing}
    {#snippet target()}
      {t("Note on:")} <strong>{app.concept(viewing)?.title}</strong>
    {/snippet}
    <PanelComposer
      id="section-note"
      value={draft}
      onvalue={(value) => app.drafts.set(draftKey, value)}
      label={t("Add a note to this section")}
      placeholder={t("Add a note to this section…")}
      submitLabel={t("Add note")}
      onsubmit={add}
      context={target}
    />
  {/if}
</section>

<style>
  .panel-list {
    gap: 0;
  }

  h3.chapter {
    margin-top: 1.4rem;
    margin-bottom: 0;
    font-size: var(--step-0);
    color: var(--ink);
  }

  h3 {
    margin: 0 0 0.5rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .group + .group,
  h3.chapter + .group {
    margin-top: 1.2rem;
  }

  h3.chapter + .group {
    margin-top: 0.5rem;
  }

  ul {
    display: grid;
    gap: 0.75rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .item {
    display: grid;
    gap: 0.35rem;
    padding: 0.6rem 0.7rem;
    border: 1px solid var(--rule);
    border-left: 3px solid var(--mine);
    border-radius: var(--radius);
    background: var(--raised);
  }

  .item.flash {
    animation: flash 1.6s ease-out;
  }

  @keyframes flash {
    0%,
    30% {
      background: var(--mine-wash);
      box-shadow: 0 0 0 0.4rem var(--mine-wash);
    }
  }

  .kind {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .where {
    font-weight: 400;
    color: var(--pencil);
  }

  blockquote {
    margin: 0;
    padding: 0.35rem 0.6rem;
    background: var(--mine-wash);
    font-family: var(--serif);
    font-size: var(--step-0);
    max-height: 7rem;
    overflow: auto;
  }

  .text {
    font-size: var(--step-0);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  textarea {
    width: 100%;
    resize: vertical;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.2rem;
  }
</style>
