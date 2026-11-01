<script lang="ts">
  import { markdown } from '../lib/markdown';
  import { diagnostic, locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import Composer from './Composer.svelte';
  import type { MemoryEntry, MemoryRequest } from '../lib/types';

  /**
   * Self-contained, so it can sit wherever it is mounted: `active` says it is on screen, and its writing box pins to the
   * bottom of whatever scrolls it (`.panel-foot` is sticky).
   */
  let { active = true }: { active?: boolean } = $props();

  // The tab shows the learner's preferences; taught terms and difficulties stay the teacher's working notes (ADR 0010).
  // A suggested preference is asked only where it was suggested, so it is left out here until confirmed.
  const preferences = $derived((app.state?.memory ?? []).filter((e) => e.kind === 'preference' && e.status === 'confirmed'));
  const requests = $derived(app.state?.memory_requests ?? []);

  let editing = $state<string | null>(null);
  let edit = $state('');

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

  // The learner says what to remember in their own words; the teacher answers and turns it into preferences.
  const viewing = $derived(app.viewingId);
  const draftKey = 'memory:ask';
  const draft = $derived(app.drafts.get(draftKey));

  async function ask(text = draft) {
    const message = text.trim();
    if (!message || !viewing) return;
    if (!(await app.askMemory(message, viewing))) return;
    if (app.drafts.get(draftKey).trim() === message) app.drafts.set(draftKey, '');
  }

  // A message just sent, or its reply, comes into view while the learner is looking.
  let seen: number | null = null;
  $effect(() => {
    const count = requests.length;
    const latest = requests.at(-1);
    if (active && latest && seen !== null && count > seen) {
      requestAnimationFrame(() => document.getElementById(`memory-request-${latest.id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }));
    }
    seen = count;
  });

  function progress(request: MemoryRequest) {
    if (request.reply) return 'answered';
    if (request.error) return 'refused';
    const status = app.turn(request.turn_id)?.status;
    return status && status !== 'running' && status !== 'completed' ? 'failed' : 'working';
  }
</script>

{#snippet editingEntry()}{t('Editing · the teacher uses this in every lesson')}{/snippet}
{#snippet target()}{t('To the teacher · say how you like to be taught')}{/snippet}

<section class="memory-panel panel-view" aria-labelledby="memory-title">
  <header class="panel-head">
    <div class="panel-bar"><h2 id="memory-title">{t('Course memory')}</h2></div>
    <p class="panel-intro">{t('How you like to be taught in this course. The teacher follows these in every lesson; tell it below what to remember or change.')}</p>
  </header>

  <div class="panel-list">
    <section class="group" id="memory-preference">
      <h3>{t('Preferences')}</h3>
      {#if !preferences.length}<p class="empty">{t('No preferences yet. Tell the teacher below how you like to be taught, or confirm one it suggests during a lesson.')}</p>{/if}
      <ul>
        {#each preferences as entry (entry.id)}
          <li class="item">
            {#if editing === entry.id}
              <Composer
                id="memory-edit-{entry.id}"
                value={edit}
                onvalue={(value) => (edit = value)}
                label={t('Preferences')}
                placeholder={t('Preferences')}
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

    {#if requests.length}
      <section class="group conversation" aria-label={t('What you asked the teacher to remember')}>
        <h3>{t('What you asked')}</h3>
        {#each requests as request (request.id)}
          {@const status = progress(request)}
          <article class="exchange" id="memory-request-{request.id}">
            <p class="asked">{request.text}</p>
            {#if status === 'answered'}
              <p class="reply">{request.reply}</p>
            {:else if status === 'working'}
              <p class="working"><span class="chip"><span class="live-dot"></span>{t('The teacher is responding')}</span></p>
            {:else}
              <p class="problem">
                {status === 'refused' ? t("The teacher's reply could not be read, so nothing changed.") : diagnostic(app.turn(request.turn_id)?.error ?? t('The response was interrupted. Please try again.'))}
                <button class="btn btn-quiet btn-small" disabled={!viewing} onclick={() => void ask(request.text)}>{t('Send again')}</button>
              </p>
            {/if}
          </article>
        {/each}
      </section>
    {/if}
  </div>

  <div class="panel-foot">
    <Composer
      id="memory-ask"
      value={draft}
      onvalue={(value) => app.drafts.set(draftKey, value)}
      label={t('Tell the teacher what to remember')}
      placeholder={t('Such as “keep answers short” or “stop giving hints when I am right”…')}
      submitLabel={t('Send')}
      onsubmit={() => void ask()}
      header={target}
      disabled={!viewing}
    />
  </div>
</section>

<style>
  .panel-list {
    gap: 1rem;
  }

  h3 {
    margin: 0 0 0.4rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

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

  .meta {
    display: flex;
    justify-content: flex-end;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem;
  }

  .conversation {
    display: grid;
    gap: 0.6rem;
  }

  .exchange {
    display: grid;
    gap: 0.35rem;
    font-size: var(--step-0);
  }

  .exchange p {
    margin: 0;
    overflow-wrap: anywhere;
  }

  /* The learner's words read like a question they asked; the teacher's answer follows plainly. */
  .asked {
    justify-self: end;
    max-width: 85%;
    padding: 0.4rem 0.65rem;
    border-radius: var(--radius);
    background: var(--accent-wash);
    color: var(--ink);
    white-space: pre-wrap;
  }

  .reply {
    color: var(--ink-soft);
  }

  .working,
  .problem {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .problem {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem 0.5rem;
    color: var(--danger);
  }
</style>
