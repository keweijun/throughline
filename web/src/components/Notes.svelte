<script lang="ts">
  import Composer from './Composer.svelte';
  import AttachedImages from './AttachedImages.svelte';
  import { slide } from 'svelte/transition';
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { noteGroups, noteLabel as label } from '../lib/notes';
  import type { Annotation } from '../lib/types';

  let scope = $state<'section' | 'chapter' | 'all'>('section');
  let search = $state('');
  let editing = $state<string | null>(null);
  // An edit is a draft like any other, so a look at another view does not lose it.
  const editKey = (id: string) => `note-edit:${id}`;
  let flash = $state<string | null>(null);

  const viewing = $derived(app.viewingId);
  // The note draft is kept per section, like the other writing boxes, so it survives a look elsewhere.
  const draftKey = $derived(`note:${viewing}`);
  const draft = $derived(app.drafts.get(draftKey));
  const words = $derived(search.toLowerCase().split(/\s+/).filter(Boolean));
  const matches = (a: Annotation) => words.every((w) => [a.passage, a.note, a.source?.label ?? ''].join(' ').toLowerCase().includes(w));
  const chapter = $derived(app.chapterOf(viewing));
  const groups = $derived.by(() => {
    const ids = scope === 'section' ? (viewing ? [viewing] : []) : scope === 'chapter' ? (chapter?.concept_ids ?? []) : (app.state?.curriculum.route ?? []);
    return noteGroups(ids, (app.state?.annotations ?? []).filter(matches), { single: scope === 'section', empty: scope === 'section' && !words.length });
  });

  // A section outside any chapter has no "This chapter" choice; fall back rather than show nothing.
  $effect(() => {
    if (scope === 'chapter' && !chapter) scope = 'section';
  });

  const total = $derived(app.state?.annotations.length ?? 0);

  async function add() {
    const section = viewing;
    const text = draft;
    const key = draftKey;
    const images = app.drafts.images(key);
    if (!section || (!text.trim() && !images.length)) return;
    if (!(await app.annotate({ kind: 'note', concept_id: section, note: text, ...(images.length ? { images } : {}) }))) return;
    if (app.drafts.get(key) === text) app.drafts.set(key, '');
    if (JSON.stringify(app.drafts.images(key)) === JSON.stringify(images)) app.drafts.setImages(key, []);
    // The new note may land mid-list when several sections are shown; bring it into view.
    const added = [...(app.state?.annotations ?? [])].reverse().find((a) => a.kind === 'note' && a.concept_id === section && a.note === text);
    if (added) app.focusAnnotation = added.id;
  }

  function start(item: Annotation) {
    app.drafts.set(editKey(item.id), item.note);
    app.drafts.setImages(editKey(item.id), item.images ?? []);
    editing = item.id;
    requestAnimationFrame(() => document.getElementById(`note-edit-${item.id}`)?.focus());
  }

  function stopEditing(item: Annotation) {
    app.drafts.set(editKey(item.id), '');
    app.drafts.setImages(editKey(item.id), []);
    if (editing === item.id) editing = null;
  }

  async function saveEdit(item: Annotation) {
    const key = editKey(item.id);
    const text = app.drafts.get(key);
    // A bookmark's note has no images, so its edit leaves them out.
    const images = item.kind === 'bookmark' ? undefined : app.drafts.images(key);
    if (item.kind === 'note' && !text.trim() && !images?.length) return;
    if (await app.editNote(item.id, text, images)) stopEditing(item);
  }

  function remove(item: Annotation) {
    if (item.note && !confirm(t("Delete this note?"))) return;
    void app.removeAnnotation(item.id);
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

{#snippet editingNote()}{t("Editing note · only you see this")}{/snippet}

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
    {#if total > 4}
      <div class="panel-tools">
        <input type="search" bind:value={search} aria-label={t("Search notes")} placeholder={t("Search your notes…")} />
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
              <Composer
                id="note-edit-{item.id}"
                value={app.drafts.get(editKey(item.id))}
                onvalue={(value) => app.drafts.set(editKey(item.id), value)}
                label={t("Note")}
                placeholder={t("Write your note…")}
                submitLabel={t("Save")}
                onsubmit={() => void saveEdit(item)}
                header={editingNote}
                onclose={() => stopEditing(item)}
                oncancel={() => stopEditing(item)}
                closeLabel={t("Cancel")}
                imagesKey={item.kind === 'bookmark' ? undefined : editKey(item.id)}
                imagesAlone={item.kind === 'note'}
                allowEmpty={item.kind !== 'note'}
              />
            {:else}
              {#if item.note}<div class="text prose" use:markdown={{ language: locale.language, text: item.note, breaks: true }}></div>{/if}
              <AttachedImages images={item.images ?? []} small />
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
      {t("Note on {section} · only you see this", { section: app.concept(viewing)?.title ?? '' })}
    {/snippet}
    <div class="panel-foot">
      <Composer
        id="section-note"
        value={draft}
        onvalue={(value) => app.drafts.set(draftKey, value)}
        label={t("Add a note to this section")}
        placeholder={t("Add a note to this section…")}
        submitLabel={t("Add note")}
        onsubmit={add}
        header={target}
        imagesKey={draftKey}
        imagesAlone
      />
    </div>
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
    overflow-wrap: anywhere;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.2rem;
  }
</style>
