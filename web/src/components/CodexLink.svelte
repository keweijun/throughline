<script lang="ts">
  import type { Snippet } from 'svelte';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio, type StudioOrigin } from '../lib/studio.svelte';

  /**
   * A hand-off of course work. In an open course it opens Studio with the request filled in (ADR 0016) and, when it
   * points somewhere, a chip naming where (`origin`); where Studio cannot run, and with `chat`, it opens a new Codex
   * chat instead.
   */
  let {
    prompt,
    class: className = '',
    chat = false,
    origin = null,
    onfollow,
    children,
  }: { prompt: string; class?: string; chat?: boolean; origin?: StudioOrigin | null; onfollow?: () => void; children: Snippet } = $props();

  const root = $derived(app.library?.root ?? '');
  /** A new Codex chat (working in the library folder) with the request typed in but not sent, so files can be attached. */
  const href = $derived(`codex://new?prompt=${encodeURIComponent(prompt)}&path=${encodeURIComponent(root)}`);
  const inStudio = $derived(!chat && !!app.state && !app.libraryOpen);

  let copied = $state(false);
  let timer: ReturnType<typeof setTimeout> | undefined;

  // The link is not handled everywhere (the Codex CLI, some Windows installs), so following it also copies the request.
  // The link itself says so for a moment, in place of its label, rather than a message elsewhere on the page.
  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt.trim());
    } catch {
      // Where the link is handled, Codex opens with the request anyway.
      return;
    }
    copied = true;
    clearTimeout(timer);
    timer = setTimeout(() => (copied = false), 4000);
  }

  $effect(() => () => clearTimeout(timer));

  async function follow(event: MouseEvent) {
    onfollow?.();
    if (!inStudio) return void copy();
    event.preventDefault();
    await studio.load();
    if (studio.available) {
      app.drafts.set('studio:new', studio.handoff(prompt, origin));
      app.showStudio({ focus: true });
      return;
    }
    void copy();
    if (root) window.location.href = href;
  }
</script>

{#if root || inStudio}
  <a
    class="codex-link {className}"
    class:studio-link={inStudio}
    class:copied
    href={root ? href : '#studio'}
    onclick={follow}
    title={copied ? t('If Codex did not open, paste it into any Codex chat.') : undefined}
  >
    <!-- Both labels share one cell, so the link keeps its width when one replaces the other. -->
    <span class="labels">
      <span class="label" aria-hidden={copied}>{@render children()}</span>
      <span class="label" aria-hidden="true">{t('Request copied')}</span>
    </span>
    <span class="visually-hidden" role="status">{#if copied}{t('Request copied')}{/if}</span>
  </a>
{/if}

<style>
  .labels {
    display: inline-grid;
  }

  .label {
    grid-area: 1 / 1;
    white-space: nowrap;
  }

  .btn .label {
    text-align: center;
  }

  a:not(.copied) .label:last-child,
  .copied .label:first-child {
    visibility: hidden;
  }

  .copied::after {
    content: '✓';
  }
</style>
