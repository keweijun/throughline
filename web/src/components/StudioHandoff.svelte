<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { newId } from '../lib/api';
  import { studio, type StudioOrigin } from '../lib/studio.svelte';
  import type { Handoff } from '../lib/types';
  import InlineConfirm from './InlineConfirm.svelte';

  /**
   * A hand-off to Studio (issue #229), the one way a fast view sends Studio what it cannot do itself. As an `offer` it
   * is a card under what raised it ("Studio can do this: …"); as a `link` it reads like any link. With full access one
   * click sends it; without, it asks once, beside it. The learner stays here: the card follows the Studio chat, working,
   * waiting on them or done, and opens it.
   */
  let {
    id = null,
    place,
    label,
    request,
    context,
    variant = 'offer',
    onsent,
  }: {
    /** A fixed id keeps the sent state across visits (a reply's offer); without one, each send is new. */
    id?: string | null;
    place: Handoff['place'];
    label: string;
    request: string;
    context: StudioOrigin;
    /** offer: a card; link: reads as a link; button: a small bordered button; chip: a pill among other choices. */
    variant?: 'offer' | 'link' | 'button' | 'chip';
    onsent?: () => void;
  } = $props();

  let sentId = $state<string | null>(null);
  let confirming = $state(false);
  let sending = $state(false);
  let problem = $state<string | null>(null);

  const sent = $derived(app.handoff(id ?? sentId ?? ''));
  const status = $derived.by(() => {
    if (!sent) return null;
    if (studio.waiting.some((r) => r.params.threadId === sent.thread_id)) return 'waiting';
    return studio.working.includes(sent.thread_id) ? 'working' : 'done';
  });

  $effect(() => {
    if (studio.access === null) void studio.loadAccess();
  });

  function start() {
    problem = null;
    if (studio.access?.full_access) void send();
    else confirming = true;
  }

  async function send() {
    confirming = false;
    if (sending) return;
    sending = true;
    const identifier = id ?? `${place.kind}:${newId()}`;
    problem = await app.handOff({ id: identifier, place, label, request }, context);
    if (!problem) {
      sentId = identifier;
      onsent?.();
    }
    sending = false;
  }
</script>

{#snippet state()}
  {#if sent}
    <span class="status" role="status">
      {#if status === 'working'}<span class="live-dot"></span>{t("Studio is working on it")}
      {:else if status === 'waiting'}{t("Studio needs your answer")}
      {:else}{t("Done in Studio")}{/if}
    </span>
    <button class="link" onclick={() => app.showStudio({ thread: sent.thread_id })}>{t("Open")}</button>
  {:else if sending}
    <span class="status" role="status"><span class="live-dot"></span>{t("Sending to Studio")}</span>
  {/if}
{/snippet}

<div class="handoff {variant}" role="group" aria-label={t("Studio: {label}", { label })}>
  {#if variant === 'offer'}
    <p class="what"><span class="badge">{t("Studio")}</span> {label}</p>
  {/if}
  {#if sent || sending}
    <p class="row actions">{@render state()}</p>
  {:else if confirming}
    <InlineConfirm
      message={t("Studio will work on your course with Codex, in its own chat: it may add files, exercises or sheets. Go ahead?")}
      confirmLabel={t("Go ahead")}
      cancelLabel={t("Not now")}
      onconfirm={send}
      oncancel={() => (confirming = false)}
    />
  {:else if variant === 'offer'}
    <button class="btn btn-small btn-primary actions" onclick={start}>{t("Do this in Studio")}</button>
  {:else if variant === 'button'}
    <button class="btn btn-small" onclick={start}>{label}</button>
  {:else if variant === 'chip'}
    <button class="chip-way" onclick={start}>↗ {label}</button>
  {:else}
    <button class="link studio-link" onclick={start}>{label}</button>
  {/if}
  {#if problem}<p class="problem">{problem} {t("The request is copied: paste it into a Codex chat.")}</p>{/if}
</div>

<style>
  /* One row: what Studio will do on the left, the action or how it is going on the right; the confirmation and any
     problem take a row of their own below. */
  .handoff.offer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 1rem;
    padding: 0.6rem 0.6rem 0.6rem 0.9rem;
    border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--rule));
    border-radius: var(--radius);
    background: var(--accent-wash);
  }

  .handoff.link,
  .handoff.button,
  .handoff.chip {
    display: grid;
    justify-items: start;
    gap: 0.3rem;
  }

  .chip-way {
    padding: 0.2rem 0.7rem;
    border: 1px solid var(--rule-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--ink-soft);
    font-size: var(--step--1);
    cursor: pointer;
  }

  .chip-way:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .what {
    flex: 1 1 14rem;
    margin: 0;
    font-size: var(--step-0);
  }

  .offer .actions {
    flex: none;
    margin-left: auto;
  }

  .offer :global(.inline-confirm),
  .offer .problem {
    flex-basis: 100%;
  }

  .badge {
    margin-right: 0.3rem;
    padding: 0.05rem 0.45rem;
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-ink, white);
    font-size: var(--step--1);
    font-weight: 600;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.9rem;
    margin: 0;
    font-size: var(--step--1);
  }

  .status {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--ink-soft);
  }

  .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
    text-align: left;
  }

  .link:hover {
    text-decoration: underline;
  }

  .studio-link::before {
    content: '↗ ';
  }

  .problem {
    margin: 0;
    font-size: var(--step--1);
    color: var(--danger);
  }
</style>
