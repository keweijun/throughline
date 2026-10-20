<script lang="ts">
  import { diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { Turn } from '../lib/types';

  let { turn, pauseLabel = 'Pause', regenerateLabel = 'Regenerate' }: { turn: Turn; pauseLabel?: string; regenerateLabel?: string } = $props();

  let busy = $state(false);

  async function run(action: () => Promise<unknown>) {
    busy = true;
    await action();
    busy = false;
  }
</script>

{#if turn.status === 'running'}
  <button class="btn btn-small" disabled={busy} onclick={() => run(() => app.pause(turn.id))}>{diagnostic(pauseLabel)}</button>
{:else if turn.status !== 'completed'}
  <button class="btn btn-small" disabled={busy} onclick={() => run(() => app.regenerate(turn.id))}>{diagnostic(regenerateLabel)}</button>
{/if}
