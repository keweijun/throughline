<script lang="ts">
  import { app } from '../lib/store.svelte';
  import { verification } from '../lib/format';
  import PdfReader from './PdfReader.svelte';
  import MarkdownReader from './MarkdownReader.svelte';

  const s = $derived(app.source);
  const v = $derived(verification(s?.verification));
  const page = $derived(s?.locator?.page);
  const where = $derived(page ? `Page ${page}` : s?.locator?.line ? `Line ${s.locator.line}` : 'Exact location missing');
  const label = $derived(s ? `${s.title}, ${page ? `p. ${page}` : `line ${s.locator?.line ?? '?'}`}` : '');
</script>

<section class="source-view">
  {#if app.sourceLoading && !s}
    <p class="muted">Opening the source…</p>
  {:else if s}
    <header>
      <h2>{s.title}</h2>
      <p class="meta">
        <span>{where}</span>
        <span class="chip chip-{v.tone}">{v.label}</span>
        {#if s.stale}<span class="chip chip-caution">Older revision of this file</span>{/if}
        {#if s.pdf_url}
          <a class="btn btn-quiet btn-small original" href={s.pdf_url} target="_blank" rel="noopener">Open original ↗</a>
        {/if}
      </p>
      {#if s.verification !== 'verified'}
        <p class="muted">Not yet checked against the original. Compare formulas and figures with the page itself. Select text to ask about it.</p>
      {/if}
    </header>

    {#if s.pdf_url && page}
      {#key s.pdf_url}
        <PdfReader url={s.pdf_url.split('#')[0]} {page} {label} />
      {/key}
    {:else if s.document}
      {#key `${s.source_id}/${s.revision}/${s.unit_id}`}
        <MarkdownReader lines={s.document} target={s.unit_id} {label} />
      {/key}
    {:else}
      <pre>{s.text || 'No text was extracted at this location.'}</pre>
    {/if}
    {#if s.render_message && !s.pdf_url}
      <p class="problem">{s.render_message}</p>
    {/if}
  {:else}
    <div class="empty">
      <p>Choose a citation in a lesson, or a source in the unit overview, to read it here.</p>
      <p class="muted">PDFs open at the cited page; Markdown notes open at the cited line.</p>
    </div>
  {/if}
</section>

<style>
  .source-view {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    flex: 1;
    min-height: 0;
  }

  header {
    display: grid;
    gap: 0.35rem;
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

  .original {
    margin-left: auto;
  }

  .muted {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .problem {
    font-size: var(--step--1);
    color: var(--danger);
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

  .empty {
    display: grid;
    gap: 0.4rem;
    margin-top: 2rem;
    text-align: center;
    color: var(--ink-soft);
    font-size: var(--step-0);
  }
</style>
