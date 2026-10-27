<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { MemoryEntry } from '../lib/types';

  // A preference the teacher suggested takes effect only once the learner confirms it (ADR 0010).
  let { entry }: { entry: MemoryEntry } = $props();
</script>

<p>{t('Remember: {text}?', { text: entry.text })}</p>
<div class="remember-actions">
  <button class="btn btn-quiet btn-small" onclick={() => app.removeMemory(entry.id)}>{t("Don't remember")}</button>
  <button class="btn btn-small" onclick={() => app.confirmMemory(entry.id)}>{t('Remember')}</button>
</div>

<style>
  .remember-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.2rem;
  }
</style>
