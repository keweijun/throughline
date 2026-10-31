<script lang="ts">
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import Composer from './Composer.svelte';
  import type { MemoryEntry } from '../lib/types';
  import SuggestedMemory from './SuggestedMemory.svelte';

  let editing = $state<string | null>(null);
  let edit = $state('');

  // The learner writes an entry down themselves. A taught term or difficulty belongs to the section being read; a
  // preference to the whole course, and needs no confirming.
  type Kind = MemoryEntry['kind'];
  let kind = $state<Kind>('preference');
  const viewing = $derived(app.viewingId);
  const draftKey = 'memory:new';
  const draft = $derived(app.drafts.get(draftKey));
  const kinds = $derived<{ kind: Kind; label: string; placeholder: string }[]>([
    { kind: 'preference', label: t('Preference'), placeholder: t('How you like to be taught, such as “short answers first”…') },
    { kind: 'taught_term', label: t('Taught term'), placeholder: t('A term or notation you already know…') },
    { kind: 'difficulty', label: t('Difficulty'), placeholder: t('An idea you keep getting wrong…') },
  ]);
  const chosen = $derived(kinds.find((k) => k.kind === kind)!);

  async function add() {
    const text = draft.trim();
    const section = kind === 'preference' ? null : viewing;
    if (!text || (kind !== 'preference' && !section)) return;
    if (!(await app.addMemory(kind, text, section))) return;
    if (app.drafts.get(draftKey).trim() === text) app.drafts.set(draftKey, '');
  }

  const entries = $derived(app.state?.memory ?? []);
  const suggested = $derived(entries.filter((e) => e.status === 'suggested'));
  const groups = $derived([
    { kind: 'preference', title: t('Preferences'), empty: t('No preferences yet. When you say how you like to be taught, the teacher asks before remembering it.') },
    { kind: 'taught_term', title: t('Taught terms'), empty: t('No terms recorded yet.') },
    { kind: 'difficulty', title: t('Difficulties'), empty: t('No difficulties recorded.') },
  ].map((g) => ({ ...g, items: entries.filter((e) => e.kind === g.kind && e.status !== 'suggested') })));

  function start(entry: MemoryEntry) {
    editing = entry.id;
    edit = entry.text;
    requestAnimationFrame(() => document.getElementById(`memory-edit-${entry.id}`)?.focus());
  }

  async function save(entry: MemoryEntry) {
    if (!edit.trim()) return;
    if (await app.editMemory(entry.id, edit)) editing = null;
  }

  function remove(entry: MemoryEntry) {
    if (confirm(t('Delete this from the course memory? The teacher will not add it back.'))) void app.removeMemory(entry.id);
  }
</script>

{#snippet editingEntry()}{t('Editing · the teacher uses this in every lesson')}{/snippet}

{#snippet target()}
  <span class="target">
    <span>{t('Remember as')}</span>
    <span class="kinds" role="radiogroup" aria-label={t('Kind of entry')}>
      {#each kinds as option (option.kind)}
        <button
          type="button"
          role="radio"
          aria-checked={kind === option.kind}
          class="kind"
          class:active={kind === option.kind}
          disabled={option.kind !== 'preference' && !viewing}
          onclick={() => (kind = option.kind)}
        >{option.label}</button>
      {/each}
    </span>
    {#if kind !== 'preference' && viewing}<span class="where">· {app.concept(viewing)?.title ?? ''}</span>{/if}
  </span>
{/snippet}

<section class="memory-panel panel-view" aria-labelledby="memory-title">
  <header class="panel-head">
    <div class="panel-bar"><h2 id="memory-title">{t('Course memory')}</h2></div>
    <p class="panel-intro">{t('What the teacher keeps about you in this course and uses in every lesson. It is not a record of mastery, and your notes are never part of it.')}</p>
  </header>

  <div class="panel-list">

  {#if suggested.length}<div class="suggestions"><SuggestedMemory entries={suggested} /></div>{/if}

  {#each groups as group (group.kind)}
    <section class="group" id="memory-{group.kind}">
      <h3>{group.title}</h3>
      {#if !group.items.length}<p class="empty">{group.empty}</p>{/if}
      <ul>
        {#each group.items as entry (entry.id)}
          <li class="item" class:cleared={entry.status === 'cleared'}>
            {#if editing === entry.id}
              <Composer
                id="memory-edit-{entry.id}"
                value={edit}
                onvalue={(value) => (edit = value)}
                label={group.title}
                placeholder={group.title}
                submitLabel={t('Save')}
                onsubmit={() => void save(entry)}
                header={editingEntry}
                onclose={() => (editing = null)}
                oncancel={() => (editing = null)}
                closeLabel={t('Cancel')}
              />
            {:else}
              <div class="text prose" use:markdown={{ language: locale.language, text: entry.text }}></div>
              <div class="meta">
                <span>{app.concept(entry.concept_id)?.title ?? ''}{#if entry.status === 'cleared'} · {t('Cleared')}{/if}</span>
                <span class="actions">
                  <button class="btn btn-quiet btn-small" onclick={() => start(entry)}>{t('Edit')}</button>
                  <button class="btn btn-quiet btn-small" onclick={() => remove(entry)}>{t('Delete')}</button>
                </span>
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    </section>
  {/each}
  </div>

  <div class="panel-foot">
    <Composer
      id="memory-new"
      value={draft}
      onvalue={(value) => app.drafts.set(draftKey, value)}
      label={t('Add to the course memory')}
      placeholder={chosen.placeholder}
      submitLabel={t('Remember')}
      onsubmit={() => void add()}
      header={target}
    />
  </div>
</section>

<style>
  .panel-list {
    gap: 0.75rem;
  }

  .target {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem 0.45rem;
  }

  .kinds {
    display: inline-flex;
    gap: 0.15rem;
  }

  .kind {
    padding: 0.05rem 0.5rem;
    border: 1px solid transparent;
    border-radius: 999px;
    background: none;
    color: var(--pencil);
    font: inherit;
    cursor: pointer;
  }

  .kind:hover:not(:disabled) {
    color: var(--ink);
  }

  .kind.active {
    border-color: color-mix(in srgb, var(--accent) 40%, var(--rule));
    background: var(--accent-wash);
    color: var(--accent);
  }

  .kind:disabled {
    opacity: 0.45;
    cursor: default;
  }

  .where {
    color: var(--pencil);
  }

  h3 {
    margin: 0.8rem 0 0.4rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .empty,
  .meta {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .suggestions :global(.suggested-memory:first-child) {
    margin-top: 0;
  }

  ul {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .item {
    display: grid;
    gap: 0.2rem;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
  }

  .item.cleared .text {
    color: var(--pencil);
  }

  .text {
    font-size: var(--step-0);
    overflow-wrap: anywhere;
  }

  .text :global(p) {
    margin: 0;
  }

  .meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.2rem;
  }
</style>
