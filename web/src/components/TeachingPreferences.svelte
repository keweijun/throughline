<script lang="ts">
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import InlineConfirm from './InlineConfirm.svelte';
  import type { MemoryEntry } from '../lib/types';

  /**
   * How the learner likes to be taught in this course: the confirmed preferences in course memory (ADR 0010), which
   * the teacher follows in every lesson. They are added where they come up (a preference the teacher suggests in a
   * lesson, or a lasting requirement told to Studio) and deleted here; changing one is asked of Studio, as adding one
   * is. Taught terms and difficulties stay the teacher's working notes.
   */
  const preferences = $derived((app.state?.memory ?? []).filter((e) => e.kind === 'preference' && e.status === 'confirmed'));

  // Deleting is confirmed beside the entry, since the teacher does not add a deleted preference back.
  let confirming = $state<string | null>(null);

  function remove(entry: MemoryEntry) {
    confirming = null;
    void app.removeMemory(entry.id);
  }
</script>

<section class="preferences" id="course-preferences" aria-labelledby="preferences-title">
  <h2 id="preferences-title">{t("How you're taught")}</h2>
  <!-- Once there are preferences they explain themselves; the way to add one is said while there are none. -->
  {#if !preferences.length}
    <p class="intro">{t('None yet. Tell Studio how you like to be taught, or confirm a preference the teacher suggests in a lesson.')}</p>
  {/if}
  {#if preferences.length}
    <ul>
      {#each preferences as entry (entry.id)}
        <li class="item">
          <div class="text prose" use:markdown={{ language: locale.language, text: entry.text }}></div>
          {#if confirming !== entry.id}
            <button class="remove" aria-label={t('Delete')} title={t('Delete')} onclick={() => (confirming = entry.id)}>
              <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M6 6l8 8M14 6l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
            </button>
          {:else}
            <div class="confirm">
              <InlineConfirm
                danger
                message={t('Delete this from the course memory? The teacher will not add it back.')}
                confirmLabel={t('Delete')}
                onconfirm={() => remove(entry)}
                oncancel={() => (confirming = null)}
              />
            </div>
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

  /* A label for the list, not a heading that competes with the course's title. */
  h2 {
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--pencil);
  }

  .intro {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  ul {
    display: grid;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* Each preference is a line of the list, with a × beside it, shown when the line is pointed at, to delete it. */
  .item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 0.25rem 0.4rem;
    padding: 0.45rem 0;
    border-top: 1px solid var(--rule);
  }

  /* In the aside's narrow column, at the size of the chats above it, so a long list stays a list to scan. */
  .text {
    font-family: var(--sans);
    font-size: var(--step--1);
    line-height: 1.45;
    overflow-wrap: anywhere;
  }

  .text :global(p) {
    margin: 0;
  }

  .remove {
    display: grid;
    place-items: center;
    width: 1.4rem;
    height: 1.4rem;
    padding: 0;
    border: 0;
    border-radius: var(--radius);
    background: none;
    color: var(--pencil);
    cursor: pointer;
  }

  .remove {
    opacity: 0;
    transition: opacity 0.15s ease;
  }

  .item:hover .remove,
  .remove:focus-visible {
    opacity: 1;
  }

  .remove:hover,
  .remove:focus-visible {
    background: var(--accent-wash);
    color: var(--danger);
  }

  .confirm {
    grid-column: 1 / -1;
  }
</style>
