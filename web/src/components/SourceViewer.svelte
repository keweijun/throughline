<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { verification } from '../lib/format';

  let imageState = $state<'loading' | 'ready' | 'failed'>('loading');

  const s = $derived(app.source);
  const v = $derived(verification(s?.verification));
  const where = $derived(s?.locator?.page ? t('Page {page}', { page: s.locator.page }) : s?.locator?.line ? t('Line {line}', { line: s.locator.line }) : 'Exact location missing');

  $effect(() => {
    void s?.image_url;
    imageState = 'loading';
  });
</script>

<section class="source-view">
  {#if app.sourceLoading}
    <p class="muted">{t("Opening the source…")}</p>
  {:else if s}
    <h2>{s.title}</h2>
    <p class="meta">
      <span>{where}</span>
      <span class="chip chip-{v.tone}">{diagnostic(v.label)}</span>
      {#if s.stale}<span class="chip chip-caution">{t("Older revision of this file")}</span>{/if}
    </p>
    {#if s.verification !== 'verified'}
      <p class="muted">{t("Not yet checked against the original. Compare formulas and figures with the page itself.")}</p>
    {/if}

    {#if s.pdf_url}
      {#if s.image_url}
        {#if imageState === 'loading'}<p class="muted">{t("Rendering the original page…")}</p>{/if}
        <img
          class="page"
          class:loaded={imageState === 'ready'}
          src={s.image_url}
          alt={t('{title}, page {page}', { title: s.title, page: s.locator?.page ?? '' })}
          onload={() => (imageState = 'ready')}
          onerror={() => (imageState = 'failed')}
          hidden={imageState === 'failed'}
        />
        {#if imageState === 'failed'}
          <p class="problem">{t("The page image could not be rendered. Open the original PDF instead.")}</p>
        {/if}
      {:else}
        <p class="problem">{s.render_message ? diagnostic(s.render_message) : t("The page image is unavailable because the source has no valid page number.")}</p>
      {/if}
      <a class="btn btn-small" href={s.pdf_url} target="_blank" rel="noopener">{t("Open the original PDF")}</a>
    {:else}
      <pre>{s.text || t("No text was extracted at this location.")}</pre>
    {/if}
  {:else}
    <p class="muted">{t("Choose a citation in a lesson, or a source in the unit overview, to see the original text here.")}</p>
  {/if}
</section>

<style>
  .source-view {
    display: grid;
    gap: 0.75rem;
  }

  h2 {
    font-size: var(--step-1);
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .muted {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .problem {
    font-size: var(--step--1);
    color: var(--danger);
  }

  .page {
    display: block;
    width: 100%;
    height: auto;
    border: 1px solid var(--rule);
    background: white;
    opacity: 0;
  }

  .page.loaded {
    opacity: 1;
  }

  pre {
    margin: 0;
    padding: 0.9rem 1rem;
    border-left: 3px solid var(--marker);
    background: var(--raised);
    font-family: var(--serif);
    font-size: var(--step-0);
    line-height: 1.7;
    white-space: pre-wrap;
  }

  a.btn {
    justify-self: start;
  }
</style>
