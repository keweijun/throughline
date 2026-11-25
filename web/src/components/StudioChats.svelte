<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { ago } from '../lib/format';
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

  const when = (seconds: number | null) => ago(seconds, now);

  // A chat just begun is listed before the list knows it.
  const listed = $derived(
    studio.threadId && !studio.thread
      ? [{ id: studio.threadId, name: '', preview: '', updated_at: Date.now() / 1000, running: studio.running }, ...studio.threads]
      : studio.threads,
  );
</script>

<!-- No chats yet: the section waits until there is one, as the chat on screen is the new one. -->
{#if listed.length}
<section class="chats" aria-labelledby="studio-chats-title">
  <div class="head">
    <h2 id="studio-chats-title">{t('Chats')}</h2>
    <button class="btn btn-quiet btn-small" disabled={!studio.threadId} onclick={() => studio.newThread()}>{t('New chat')}</button>
  </div>
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
</section>
{/if}

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

  /* A label for the list, not a heading that competes with the course's title. */
  h2 {
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--pencil);
  }

  /* Long lists scroll on their own, so how the learner is taught stays in reach below. */
  ul {
    display: grid;
    /* One column no wider than the list, so a long title is cut with an ellipsis and never pushes the time out of view. */
    grid-template-columns: minmax(0, 1fr);
    gap: 0.1rem;
    max-height: 18rem;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    list-style: none;
  }

  li {
    animation: enter-fade var(--settle) ease;
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
    font-size: var(--step--2);
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
