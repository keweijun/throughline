<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import type { Sheet } from '../lib/types';
  import CodexLink from './CodexLink.svelte';
  import InlineConfirm from './InlineConfirm.svelte';

  /**
   * A sheet Studio wrote (issue #229), read in Review: what it covers and when it was written on top, to print or to
   * change in Studio, and to remove when it is no longer wanted.
   */
  let { sheet }: { sheet: Sheet } = $props();

  let removing = $state(false);
  const covers = $derived(
    [...(sheet.scope.chapter_ids ?? []).map((id) => app.chapters.find((c) => c.id === id)?.title ?? id),
     ...(sheet.scope.concept_ids ?? []).map((id) => app.concept(id)?.title ?? id)].join(', ') || t("The whole course"),
  );
  const when = $derived(new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(sheet.updated_at * 1000)));
  const course = $derived(app.libraryCourse);

  // Printing shows this sheet alone: the page marks it, and the print styles hide everything else.
  function print() {
    document.body.dataset.print = sheet.id;
    window.addEventListener('afterprint', () => delete document.body.dataset.print, { once: true });
    window.print();
  }
</script>

<article class="sheet-view" data-sheet={sheet.id} aria-labelledby="sheet-{sheet.id}">
  <header>
    <div>
      <h2 id="sheet-{sheet.id}">{sheet.title}</h2>
      <p class="meta">{covers} · {when}</p>
    </div>
    <div class="actions">
      {#if course}
        <CodexLink class="btn btn-quiet btn-small" prompt={t('$throughline change the sheet "{title}" (sheet {id}) in the course {course}: ', { title: sheet.title, id: sheet.id, course: course.name })} origin={{ label: t('Sheet: {title}', { title: sheet.title }), text: `sheet "${sheet.title}" (${sheet.id})` }}>{t("Change in Studio")}</CodexLink>
      {/if}
      <button class="btn btn-quiet btn-small" onclick={print}>{t("Print")}</button>
      <button class="btn btn-quiet btn-small" onclick={() => (removing = true)}>{t("Remove")}</button>
    </div>
  </header>
  {#if removing}
    <InlineConfirm message={t("Remove this sheet? Studio can write it again.")} confirmLabel={t("Remove")} cancelLabel={t("Keep it")} danger onconfirm={() => app.deleteSheet(sheet.id)} oncancel={() => (removing = false)} />
  {/if}
  <div class="prose body" use:markdown={{ language: locale.language, text: sheet.markdown }}></div>
</article>

<style>
  /* Named at the top as every view of the Review place is; the sheet itself is the paper under it. */
  .sheet-view {
    display: grid;
    gap: 1.5rem;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 1.25rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--rule);
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
    line-height: 1.2;
  }

  .meta {
    margin-top: 0.3rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem;
  }

  .body {
    padding: 1.3rem 1.5rem 1.5rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
    font-size: var(--step-0);
    line-height: 1.6;
  }
</style>
