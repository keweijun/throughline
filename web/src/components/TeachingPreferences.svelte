<script lang="ts">
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import Composer from './Composer.svelte';
  import type { MemoryEntry } from '../lib/types';

  /**
   * How the learner likes to be taught in this course: the confirmed preferences in course memory (ADR 0010), which
   * the teacher follows in every lesson. They are added where they come up (a preference the teacher suggests in a
   * lesson, or a lasting requirement told to Studio) and edited or deleted here. Taught terms and difficulties stay
   * the teacher's working notes.
   */
  const preferences = $derived((app.state?.memory ?? []).filter((e) => e.kind === 'preference' && e.status === 'confirmed'));

  let editing = $state<string | null>(null);
  let edit = $state('');

  function start(entry: MemoryEntry) {
    editing = entry.id;
    edit = entry.text;
    requestAnimationFrame(() => document.getElementById(`preference-edit-${entry.id}`)?.focus());
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

<section class="preferences" id="course-preferences" aria-labelledby="preferences-title">
  <h2 id="preferences-title">{t("How you're taught")}</h2>
  <p class="intro">{t('The teacher follows these in every lesson. To add or change one, tell Studio, or confirm one the teacher suggests during a lesson.')}</p>
  {#if !preferences.length}
    <p class="empty">{t('Nothing yet.')}</p>
  {:else}
    <ul>
      {#each preferences as entry (entry.id)}
        <li class="item">
          {#if editing === entry.id}
            <Composer
              id="preference-edit-{entry.id}"
              value={edit}
              onvalue={(value) => (edit = value)}
              label={t("How you're taught")}
              placeholder={t("How you're taught")}
              submitLabel={t('Save')}
              onsubmit={() => void save(entry)}
              header={editingEntry}
              onclose={() => (editing = null)}
              oncancel={() => (editing = null)}
              closeLabel={t('Cancel')}
            />
          {:else}
            <div class="text prose" use:markdown={{ language: locale.language, text: entry.text }}></div>
            <span class="actions">
              <button class="btn btn-quiet btn-small" onclick={() => start(entry)}>{t('Edit')}</button>
              <button class="btn btn-quiet btn-small" onclick={() => remove(entry)}>{t('Delete')}</button>
            </span>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .preferences {
    display: grid;
    gap: 0.6rem;
    align-content: start;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .intro,
  .empty {
    font-size: var(--step--1);
    color: var(--pencil);
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

  .text {
    font-size: var(--step-0);
    overflow-wrap: anywhere;
  }

  .text :global(p) {
    margin: 0;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.2rem;
  }
</style>
