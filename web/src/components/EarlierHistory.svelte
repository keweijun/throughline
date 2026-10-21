<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';

  // Messages recorded by chat sessions (the Codex skill); this interface's own records use these prefixes.
  const own = /^(stream|stream-user|practice-[a-z-]+):/;
  const items = $derived((app.state?.session.recent_interactions ?? []).filter((i) => !own.test(i.id)));
</script>

{#if items.length}
  <details class="history">
    <summary>{t("Earlier conversation from chat sessions")}</summary>
    {#each items as item (item.id)}
      <div class="item">
        <p class="who">{item.role === 'assistant' ? t("Teacher") : t("You")}</p>
        <div class="prose" use:markdown={{ language: locale.language, text: item.text }}></div>
      </div>
    {/each}
  </details>
{/if}

<style>
  .history {
    margin-top: 3rem;
    font-size: var(--step-0);
  }

  summary {
    cursor: pointer;
    color: var(--pencil);
  }

  .item {
    margin-top: 1.25rem;
  }

  .who {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
    margin-bottom: 0.25rem;
  }

  .prose {
    font-size: var(--step-0);
  }
</style>
