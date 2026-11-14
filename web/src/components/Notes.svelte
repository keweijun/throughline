<script lang="ts">
  import Composer from './Composer.svelte';
  import AttachedImages from './AttachedImages.svelte';
  import PanelGroups from './PanelGroups.svelte';
  import PanelScope from './PanelScope.svelte';
  import { groupBySection, scopeCounts, type PanelScope as Scope } from '../lib/panel';
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { noteLabel as label } from '../lib/notes';
  import type { Annotation } from '../lib/types';

  // Questions and Notes narrow and search their lists the same way.
  let scope = $state<Scope>('section');
  let scopeChosen = false;
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
  // Notes on a chapter recap or quiz question belong to their chapter, not the section they were written from.
  const ownerOf = (a: Annotation) => app.ownerChapter(a);
  const sectionOf = (a: Annotation) => a.concept_id;
  const all = $derived(app.state?.annotations ?? []);
  const counts = $derived(scopeCounts(all, sectionOf, ownerOf));
  // Until the learner picks a scope, show the narrowest one that has something in it.
  $effect(() => {
    if (!scopeChosen) scope = counts.section ? 'section' : counts.chapter ? 'chapter' : 'all';
  });
  const groups = $derived(groupBySection(all.filter(matches), scope, sectionOf, ownerOf));
  const shown = $derived(groups.reduce((n, g) => n + g.items.length, 0));


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
    if (!id || !app.panelShown || app.panelTab !== 'notes') return;
    const item = app.state?.annotations.find((a) => a.id === id);
    if (item && !matches(item)) search = '';
    if (item && (item.concept_id !== viewing || app.ownerChapter(item))) {
      scope = 'all';
      scopeChosen = true;
    }
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
    <div class="panel-bar"><h2 id="notes-title">{t("Your notes")}</h2></div>
    <p class="panel-intro">{t("Select text in a lesson or source to highlight it or add a note. Only you see these; the teacher does not.")}</p>
    {#if total}
      <PanelScope bind:scope {counts} label={t("Show notes from")} onchoose={() => (scopeChosen = true)} />
    {/if}
    {#if total > 4}
      <div class="panel-tools">
        <input type="search" bind:value={search} aria-label={t("Search notes")} placeholder={t("Search your notes…")} />
      </div>
    {/if}
  </header>

  <div class="panel-list">
    {#snippet note(item: Annotation)}
      <article id="annotation-{item.id}" class="item {item.kind}" class:flash={flash === item.id}>
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
      </article>
    {/snippet}
    <PanelGroups
      {groups}
      {scope}
      key={(a) => a.id}
      item={note}
      empty={words.length ? t("No notes match your search.") : !total ? t("No highlights, notes or bookmarks yet.") : scope === 'chapter' ? t("No notes in this chapter yet.") : t("No notes in this section yet.")}
    />
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
        compact
        imagesKey={draftKey}
        imagesAlone
      />
    </div>
  {/if}
</section>

<style>
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
