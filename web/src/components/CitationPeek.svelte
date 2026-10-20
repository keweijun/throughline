<script lang="ts">
  import { app } from '../lib/store.svelte';
  import { verification } from '../lib/format';
  import type { Ref, SourceView } from '../lib/types';

  let view = $state<SourceView | null>(null);
  let failed = $state(false);
  let left = $state(0);
  let top = $state(0);
  let above = $state(false);
  let anchor: HTMLElement | null = null;
  let showTimer: ReturnType<typeof setTimeout> | undefined;
  let hideTimer: ReturnType<typeof setTimeout> | undefined;
  let open = $state(false);

  const v = $derived(verification(view?.verification));
  const excerpt = $derived.by(() => {
    const text = (view?.text ?? '').replace(/\s+/g, ' ').trim();
    return text.length > 320 ? text.slice(0, 320).replace(/\s\S*$/, '') + '…' : text;
  });

  function citation(target: EventTarget | null) {
    return target instanceof Element ? target.closest<HTMLElement>('.citation[data-ref]') : null;
  }

  function enter(event: Event) {
    const button = citation(event.target);
    if (!button) return;
    clearTimeout(hideTimer);
    clearTimeout(showTimer);
    showTimer = setTimeout(() => show(button), event.type === 'focusin' ? 0 : 280);
  }

  function leave(event: Event) {
    if (!citation(event.target) && !(event.target as Element)?.closest?.('.peek')) return;
    clearTimeout(showTimer);
    hideTimer = setTimeout(() => (open = false), 180);
  }

  async function show(button: HTMLElement) {
    anchor = button;
    const ref = JSON.parse(button.dataset.ref!) as Ref;
    const rect = button.getBoundingClientRect();
    above = rect.bottom + 220 > window.innerHeight;
    left = Math.max(12, Math.min(rect.left - 20, window.innerWidth - 352));
    top = above ? rect.top - 10 : rect.bottom + 10;
    view = null;
    failed = false;
    open = true;
    try {
      const result = await app.sourceView(ref);
      if (anchor === button) view = result;
    } catch {
      if (anchor === button) failed = true;
    }
  }
</script>

<svelte:document
  onpointerover={enter}
  onpointerout={leave}
  onfocusin={enter}
  onfocusout={leave}
  onkeydown={(e) => e.key === 'Escape' && (open = false)}
/>
<svelte:window onscrollcapture={() => (open = false)} />

{#if open}
  <div
    class="peek"
    class:above
    style:left="{left}px"
    style:top="{top}px"
    role="tooltip"
    onpointerenter={() => clearTimeout(hideTimer)}
  >
    {#if failed}
      <p class="muted">This source location could not be loaded.</p>
    {:else if !view}
      <p class="muted">Looking up the source…</p>
    {:else}
      <p class="head">
        <span class="title">{view.title}</span>
        <span class="where">{view.locator?.page ? `p. ${view.locator.page}` : `line ${view.locator?.line}`}</span>
      </p>
      {#if excerpt}<blockquote>{excerpt}</blockquote>{:else}<p class="muted">No text was extracted at this location.</p>{/if}
      <p class="foot">
        <span class="chip chip-{v.tone}">{v.label}</span>
        <span class="muted">Click to open in the reader</span>
      </p>
    {/if}
  </div>
{/if}

<style>
  .peek {
    position: fixed;
    z-index: 60;
    display: grid;
    gap: 0.5rem;
    width: min(21rem, calc(100vw - 24px));
    padding: 0.8rem 0.9rem;
    border: 1px solid var(--rule-strong);
    border-radius: 8px;
    background: var(--raised);
    box-shadow: var(--shadow);
    font-size: var(--step--1);
    animation: rise 0.14s ease-out;
  }

  .peek.above {
    transform: translateY(-100%);
    animation-name: drop;
  }

  @keyframes rise {
    from {
      opacity: 0;
      translate: 0 4px;
    }
  }

  @keyframes drop {
    from {
      opacity: 0;
      translate: 0 -4px;
    }
  }

  .head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .title {
    font-weight: 600;
    color: var(--ink);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .where {
    flex: none;
    color: var(--pencil);
    font-variant-numeric: tabular-nums;
  }

  blockquote {
    margin: 0;
    padding-left: 0.7rem;
    border-left: 3px solid var(--marker);
    font-family: var(--serif);
    font-size: var(--step-0);
    line-height: 1.55;
    color: var(--ink);
  }

  .foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .muted {
    color: var(--pencil);
  }
</style>
