<script lang="ts">
  import type { Snippet } from 'svelte';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  let { prompt, class: className = '', children }: { prompt: string; class?: string; children: Snippet } = $props();

  const root = $derived(app.library?.root ?? '');
  /** A new Codex chat (working in the library folder) with the request typed in but not sent, so files can be attached. */
  const href = $derived(`codex://new?prompt=${encodeURIComponent(prompt)}&path=${encodeURIComponent(root)}`);

  // The link is not handled everywhere (the Codex CLI, some Windows installs), so following it also copies the request.
  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt.trim());
      app.notify(t('Request copied'), t('If Codex did not open, paste it into any Codex chat.'));
    } catch {
      // Where the link is handled, Codex opens with the request anyway.
    }
  }
</script>

{#if root}<a class="codex-link {className}" {href} onclick={copy}>{@render children()}</a>{/if}
