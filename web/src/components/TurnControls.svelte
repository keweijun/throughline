<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { Turn } from '../lib/types';

  let { turn, pauseLabel, regenerateLabel }: { turn: Turn; pauseLabel?: string; regenerateLabel?: string } = $props();

  // Stays busy until the refreshed turn shows the result, so a second click cannot repeat the request.
  let busy = $state(false);

  async function run(action: () => Promise<unknown>) {
    if (busy) return;
    busy = true;
    await action();
    busy = false;
  }
</script>

{#if turn.status === 'running'}
  <button class="btn btn-small" disabled={busy} onclick={() => run(() => app.pause(turn.id))}>{pauseLabel ?? t('Pause')}</button>
{:else if turn.status !== 'completed'}
  <button class="btn btn-small" disabled={busy} onclick={() => run(() => app.regenerate(turn.id))}>{regenerateLabel ?? t('Regenerate')}</button>
{/if}
