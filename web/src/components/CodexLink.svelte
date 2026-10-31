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
    children,
  }: { prompt: string; class?: string; chat?: boolean; origin?: StudioOrigin | null; children: Snippet } = $props();

  const root = $derived(app.library?.root ?? '');
  /** A new Codex chat (working in the library folder) with the request typed in but not sent, so files can be attached. */
  const href = $derived(`codex://new?prompt=${encodeURIComponent(prompt)}&path=${encodeURIComponent(root)}`);
  const inStudio = $derived(!chat && !!app.state && !app.libraryOpen);

  // The link is not handled everywhere (the Codex CLI, some Windows installs), so following it also copies the request.
  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt.trim());
      app.notify(t('Request copied'), t('If Codex did not open, paste it into any Codex chat.'));
    } catch {
      // Where the link is handled, Codex opens with the request anyway.
    }
  }

  async function follow(event: MouseEvent) {
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

{#if root || inStudio}<a class="codex-link {className}" class:studio-link={inStudio} href={root ? href : '#studio'} onclick={follow}>{@render children()}</a>{/if}
