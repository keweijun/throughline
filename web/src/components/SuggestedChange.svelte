<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import CodexLink from './CodexLink.svelte';

  // A change to the course itself the teacher suggested in this reply (ADR 0016), asked right after it, where the
  // learner is reading. Opening it fills Studio with the request and a chip naming the section; either choice closes it.
  let { turnId }: { turnId: string } = $props();

  const change = $derived(app.changeBy(turnId));
  const section = $derived(change ? app.concept(change.concept_id) : undefined);
</script>

{#if change}
  <div class="suggested-change" role="group" aria-label={t('Suggested course change')}>
    <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M4 15.5l1-3.5 8-8 2.5 2.5-8 8zM11.5 5.5l2.5 2.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" /></svg>
    <p>{t('Change the course? {request}', { request: change.request })}</p>
    <div class="change-actions">
      <button class="btn btn-quiet btn-small" onclick={() => app.resolveChange(change.id, 'dismissed')}>{t('Not now')}</button>
      <CodexLink
        class="btn btn-small"
        prompt={`$throughline ${change.request}`}
        origin={section ? { label: t('Section: {section}', { section: section.title }), text: `section "${section.title}" (${section.id})` } : null}
        onfollow={() => app.resolveChange(change.id, 'opened')}
      >{t('Open in Studio')}</CodexLink>
    </div>
  </div>
{/if}

<style>
  /* Drawn like a suggested preference (SuggestedMemory), the other question the teacher asks under a reply. */
  .suggested-change {
    animation: enter-rise var(--settle) var(--ease-out);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.6rem;
    margin-top: 1rem;
    padding: 0.55rem 0.6rem 0.55rem 0.8rem;
    border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--rule));
    border-radius: var(--radius);
    background: var(--accent-wash);
    font-size: var(--step-0);
  }

  svg {
    flex: none;
    color: var(--accent);
  }

  p {
    flex: 1;
    min-width: 12rem;
    margin: 0;
    color: var(--ink);
  }

  .change-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.2rem;
  }

  .suggested-change :global(.btn:not(.btn-quiet)) {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
  }

  .suggested-change :global(.btn:not(.btn-quiet):hover) {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
  }

  @media (prefers-reduced-motion: reduce) {
    .suggested-change {
      animation: none;
    }
  }
</style>
