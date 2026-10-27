<script lang="ts">
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { autogrow } from '../lib/autogrow';
  import { enterToSend } from '../lib/keys';
  import type { MemoryEntry } from '../lib/types';
  import RememberPrompt from './RememberPrompt.svelte';

  let editing = $state<string | null>(null);
  let edit = $state('');

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
  }

  async function save(entry: MemoryEntry) {
    if (!edit.trim()) return;
    if (await app.editMemory(entry.id, edit)) editing = null;
  }

  function remove(entry: MemoryEntry) {
    if (confirm(t('Delete this from the course memory? The teacher will not add it back.'))) void app.removeMemory(entry.id);
  }
</script>

<section class="memory-panel" aria-labelledby="memory-title">
  <h2 id="memory-title">{t('Course memory')}</h2>
  <p class="intro">{t('What the teacher keeps about you in this course and uses in every lesson. It is not a record of mastery, and your notes are never part of it.')}</p>

  {#each suggested as entry (entry.id)}
    <div class="suggested" role="group" aria-label={t('Suggested preference')}>
      <RememberPrompt {entry} />
    </div>
  {/each}

  {#each groups as group (group.kind)}
    <section class="group" id="memory-{group.kind}">
      <h3>{group.title}</h3>
      {#if !group.items.length}<p class="empty">{group.empty}</p>{/if}
      <ul>
        {#each group.items as entry (entry.id)}
          <li class="item" class:cleared={entry.status === 'cleared'}>
            {#if editing === entry.id}
              <textarea
                rows="2"
                bind:value={edit} use:autogrow={edit}
                aria-label={group.title}
                use:enterToSend={() => void save(entry)}
                onkeydown={(e) => e.key === 'Escape' && (editing = null)}
              ></textarea>
              <div class="actions">
                <button class="btn btn-quiet btn-small" onclick={() => (editing = null)}>{t('Cancel')}</button>
                <button class="btn btn-small" onclick={() => save(entry)}>{t('Save')}</button>
              </div>
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
</section>

<style>
  .memory-panel {
    display: grid;
    gap: 0.75rem;
  }

  h2 {
    font-size: var(--step-1);
    font-weight: 600;
  }

  h3 {
    margin: 0.8rem 0 0.4rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .intro,
  .empty,
  .meta {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .suggested {
    display: grid;
    gap: 0.4rem;
    padding: 0.6rem 0.7rem;
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    background: var(--accent-wash);
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
