<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { studio } from '../lib/studio.svelte';

  /**
   * The course's Studio chats beside Studio, as Codex lists its threads: a new chat, then each chat by its title, with
   * a dot while Codex works in it and when it was last used. The open chat is marked; picking one opens it in Studio.
   */
  let now = $state(Date.now());
  $effect(() => {
    const clock = setInterval(() => (now = Date.now()), 60_000);
    return () => clearInterval(clock);
  });

  function when(seconds: number | null) {
    if (!seconds) return '';
    const minutes = Math.round((seconds * 1000 - now) / 60_000);
    const format = new Intl.RelativeTimeFormat(locale.language, { numeric: 'auto', style: 'narrow' });
    if (Math.abs(minutes) < 60) return format.format(Math.min(minutes, 0), 'minute');
    if (Math.abs(minutes) < 60 * 24) return format.format(Math.round(minutes / 60), 'hour');
    return format.format(Math.round(minutes / (60 * 24)), 'day');
  }

  // A chat just begun is listed before the list knows it.
  const listed = $derived(
    studio.threadId && !studio.thread
      ? [{ id: studio.threadId, name: '', preview: '', updated_at: Date.now() / 1000, running: studio.running }, ...studio.threads]
      : studio.threads,
  );
</script>

<section class="chats" aria-labelledby="studio-chats-title">
  <div class="head">
    <h2 id="studio-chats-title">{t('Chats')}</h2>
    <button class="btn btn-small" disabled={!studio.threadId} onclick={() => studio.newThread()}>{t('New chat')}</button>
  </div>
  {#if listed.length}
    <ul>
      {#each listed as thread (thread.id)}
        <li>
          <button class="chat" aria-current={thread.id === studio.threadId ? 'true' : undefined} onclick={() => thread.id !== studio.threadId && void studio.open(thread.id)}>
            <span class="name">{studio.label(thread.id)}</span>
            {#if thread.running || studio.working.includes(thread.id)}
              <span class="dot" title={t('Codex is working')} aria-label={t('Codex is working')}></span>
            {:else}
              <span class="when">{when(thread.updated_at)}</span>
            {/if}
          </button>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="empty">{t('Nothing yet.')}</p>
  {/if}
</section>

<style>
  .chats {
    display: grid;
    gap: 0.6rem;
    align-content: start;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .empty {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  /* Long lists scroll on their own, so how the learner is taught stays in reach below. */
  ul {
    display: grid;
    gap: 0.1rem;
    max-height: 18rem;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    list-style: none;
  }

  .chat {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    width: 100%;
    padding: 0.35rem 0.55rem;
    border: 0;
    border-radius: var(--radius);
    background: none;
    color: var(--ink-soft);
    font: inherit;
    font-size: var(--step--1);
    text-align: left;
    cursor: pointer;
  }

  .chat:hover {
    background: var(--raised);
    color: var(--ink);
  }

  .chat[aria-current='true'] {
    background: var(--accent-wash);
    color: var(--ink);
    font-weight: 600;
  }

  .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .when {
    flex: none;
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--pencil);
  }

  .dot {
    flex: none;
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.2s ease-in-out infinite;
  }

  @keyframes pulse {
    50% {
      opacity: 0.3;
    }
  }
</style>
