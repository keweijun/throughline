<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { verification } from '../lib/format';
  import { annotationPassage } from '../lib/highlight';
  import PdfReader from './PdfReader.svelte';
  import MarkdownReader from './MarkdownReader.svelte';
  import CodexLink from './CodexLink.svelte';
  import SourceList from './SourceList.svelte';

  /** On the Overview's Sources tab the list stands beside the reader, so the reader never swaps to it. */
  let { page: inPage = false }: { page?: boolean } = $props();

  const s = $derived(app.source);
  const listed = $derived(!inPage && (app.sourceList || (!s && !app.sourceLoading)));
  // Why an unchecked location needs care, and the way to have it checked, unfold from its status.
  let details = $state(false);
  const v = $derived(verification(s?.verification));
  const page = $derived(s?.locator?.page);
  let shown = $state(1);
  $effect(() => {
    if (page) shown = page;
  });
  const where = $derived(page ? t('Page {page}', { page }) : s?.locator?.line ? t('Line {line}', { line: s.locator.line }) : t('Exact location missing'));
  const course = $derived(app.libraryCourse);
  const label = $derived(s ? `${s.title}, ${page ? t('p. {page}', { page }) : t('line {line}', { line: s.locator?.line ?? '?' })}` : '');
  const mine = $derived(
    (app.state?.annotations ?? []).filter(
      (a) => a.kind !== 'bookmark' && a.source?.source_id === s?.source_id && a.source?.revision === s?.revision,
    ),
  );
  const pageRef = $derived(
    s
      ? s.pdf_url && page
        ? { source_id: s.source_id, revision: s.revision, unit_id: `page-${shown}`, page: shown, label: `${s.title}, ${t('p. {page}', { page: shown })}` }
        : { source_id: s.source_id, revision: s.revision, unit_id: s.unit_id, label }
      : null,
  );
  const concept = $derived(app.viewingId);
  const marked = $derived(!!(concept && pageRef && app.bookmark(concept, pageRef)));
</script>

<section class="source-view" aria-busy={app.sourceLoading}>
  {#if listed}
    <SourceList />
  {/if}
  <!-- The open document stays mounted behind the list, so returning keeps its page and zoom. -->
  <div class="reading" hidden={listed}>
  {#if app.sourceLoading && !s}
    <p class="muted">{t("Opening the source…")}</p>
  {:else if s}
    {#if app.sourceLoading}<p class="switching" role="status">{t("Opening the source…")}</p>{/if}
    <!-- One line, so the document has the height: what it is, where, and whether it was checked. -->
    <header>
      <div class="headline" class:in-panel={!inPage}>
        {#if !inPage}
          <button class="btn btn-quiet btn-small btn-flush all" onclick={() => (app.sourceList = true)} title={t("All sources ({count})", { count: app.state?.sources.length ?? 0 })}>
            <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M12 5l-5 5 5 5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
            {t("All sources ({count})", { count: app.state?.sources.length ?? 0 })}
          </button>
        {/if}
        <h2 title={s.title}>{s.title}</h2>
        <span class="where">{where}</span>
        {#if s.verification !== 'verified'}
          <button class="chip chip-{v.tone} status" aria-expanded={details} onclick={() => (details = !details)}>
            {t(v.label)}
            <svg viewBox="0 0 20 20" width="12" height="12" aria-hidden="true"><path d="M5.5 8l4.5 4.5L14.5 8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
          </button>
        {:else}
          <span class="chip chip-{v.tone}">{t(v.label)}</span>
        {/if}
        {#if s.converted_from}<span class="chip" title={t("Converted so it can be shown here. The original is kept in the course.")}>{t("From {name}", { name: s.converted_from })}</span>{/if}
        {#if s.stale}<span class="chip chip-caution">{t("Older revision of this file")}</span>{/if}
        {#if !(s.pdf_url && page)}<span class="end">{@render tools()}</span>{/if}
        {#if inPage}
          <button class="btn btn-quiet btn-small close" onclick={() => (app.source = null)} aria-label={t("Close {title}", { title: s.title })} title={t("Close")}>
            <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" /></svg>
          </button>
        {/if}
      </div>
      {#if details && s.verification !== 'verified'}
        <div class="details">
          <p class="muted">{t("Not yet checked against the original. Compare formulas and figures with the page itself. Select text to ask about it.")}</p>
          {#if course}
            <p class="muted">
              <CodexLink prompt={t('$throughline review {location} (source {source}, unit {unit}) in the course {course}', { location: label, source: s.source_id, unit: s.unit_id, course: course.name })} origin={{ label, text: `source ${s.source_id}, unit ${s.unit_id} (${label})` }}>
                {t('Check this location in Studio')}
              </CodexLink>
            </p>
          {/if}
        </div>
      {/if}
    </header>

    {#if s.pdf_url && page}
      <!-- Keyed on the document, not the cited page, so citations into the same PDF keep its zoom and only scroll. -->
      {#key `${s.source_id}/${s.revision}`}
        <PdfReader
          url={s.pdf_url.split('#')[0]}
          document="{s.source_id}/{s.revision}"

          {page}
          {label}
          bind:current={shown}
          pageImages={s.image_url && s.pages
            ? { count: s.pages, url: (n) => `/api/sources/${s.source_id}/${s.revision}/page-${n}?format=image` }
            : null}
          highlights={mine.map((a) => ({ page: Number(a.source!.unit_id.replace('page-', '')), passage: annotationPassage(a) }))}
          {tools}
        />
      {/key}
    {:else if s.document}
      {#key `${s.source_id}/${s.revision}/${s.unit_id}`}
        <MarkdownReader lines={s.document} target={s.unit_id} {label} highlights={mine.map(annotationPassage)} />
      {/key}
    {:else}
      <pre>{s.text || t("No text was extracted at this location.")}</pre>
    {/if}
    {#if s.render_message && !s.pdf_url}
      <p class="problem">{diagnostic(s.render_message)}</p>
    {/if}
  {/if}
  </div>
</section>

<!-- The bookmark and the original sit with the PDF's own controls, or at the end of the header for a text. -->
{#snippet tools()}
  {#if s && concept && pageRef}
    <button
      class="btn btn-quiet btn-small icon bookmark"
      aria-pressed={marked}
      aria-label={marked ? t("Bookmarked") : page ? t("Bookmark page") : t("Bookmark line")}
      onclick={() => app.toggleBookmark(concept, pageRef)}
      title="{marked ? t('Bookmarked') : page ? t('Bookmark page') : t('Bookmark line')}. {t('Bookmarks are yours. The teacher does not see them.')}"
    >
      <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5.5 3.5h9v13l-4.5-3.2-4.5 3.2z" fill={marked ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
    </button>
  {/if}
  {#if s?.pdf_url}
    <a class="btn btn-quiet btn-small icon original" href={s.pdf_url} target="_blank" rel="noopener" aria-label={s.converted_from ? t("Open PDF ↗") : t("Open original ↗")} title={s.converted_from ? t("Open PDF ↗") : t("Open original ↗")}>
      <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M11 3.5h5.5V9M16.5 3.5L9 11M14 12v4.5H3.5V6H8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </a>
  {/if}
{/snippet}

<style>
  .source-view {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    flex: 1;
    min-height: 0;
  }

  .reading {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    flex: 1;
    min-height: 0;
  }

  .reading[hidden] {
    display: none;
  }

  .all {
    gap: 0.2rem;
  }

  header {
    display: grid;
    gap: 0.35rem;
  }

  .headline {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.5rem;
    min-width: 0;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .headline > * {
    flex: none;
  }

  /* The chips wrap to a second row before the title shrinks; only a title longer than the whole line is cut, and the
     whole of it is in the tooltip. */
  .headline h2 {
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .where {
    font-variant-numeric: tabular-nums;
  }

  .status {
    border: 0;
    font: inherit;
    font-size: var(--step--1);
    font-weight: 500;
    cursor: pointer;
  }

  .status svg {
    transition: transform var(--quick) var(--ease-out);
  }

  .status[aria-expanded='true'] svg {
    transform: rotate(180deg);
  }

  .end {
    display: flex;
    align-items: center;
    gap: 0.15rem;
    margin-left: auto;
  }

  .close {
    margin-left: auto;
    padding: 0.2rem;
  }

  .end + .close {
    margin-left: 0;
  }

  .details {
    display: grid;
    gap: 0.25rem;
  }

  .details p {
    margin: 0;
  }

  .switching {
    align-self: flex-start;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    background: var(--accent-wash);
    color: var(--accent);
    font-size: var(--step--1);
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink);
  }

  .icon {
    padding: 0.25rem 0.35rem;
  }

  /* The side panel's own close button sits at the end of this line. */
  .headline.in-panel {
    padding-right: 2rem;
  }

  .bookmark[aria-pressed='true'] {
    color: var(--mine);
    font-weight: 600;
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

</style>
