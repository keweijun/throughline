<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { Ref } from '../lib/types';

  type Entry = {
    id: string;
    name: string;
    kind: string;
    status: string;
    sections: string[];
    target: Ref | null;
    notes: number;
  };

  const route = $derived(app.state?.curriculum.route ?? []);
  const coverage = $derived(app.state?.curriculum.coverage ?? []);

  // Every registered document, opened where the section being read uses it, otherwise at its beginning.
  const entries = $derived.by((): Entry[] =>
    (app.state?.sources ?? []).map((source) => {
      const units = coverage.filter((c) => c.source_id === source.id && c.revision === source.revision);
      // A section uses a document if the coverage ledger maps it there or the section links to it directly.
      const linked = (id: string) => [...(app.concept(id)?.links ?? []), ...(app.concept(id)?.exercises ?? [])].some((r) => r.source_id === source.id);
      const sections = route.filter((id) => units.some((u) => u.concept_ids?.includes(id)) || linked(id));
      const name = source.path.split(/[\\/]/).pop() ?? source.path;
      const kind = name.toLowerCase().endsWith('.pdf') ? 'PDF' : name.split('.').pop()?.toUpperCase() ?? '';
      const link = app.concept(app.viewingId)?.links?.find((r) => r.source_id === source.id && r.revision === source.revision);
      const here = units.find((u) => u.concept_ids?.includes(app.viewingId ?? '')) ?? link ?? units[0];
      const unit = here?.unit_id ?? (kind === 'PDF' ? 'page-1' : 'line-1');
      return {
        id: source.id,
        name,
        kind,
        status: source.status,
        sections,
        target: source.revision ? { source_id: source.id, revision: source.revision, unit_id: unit } : null,
        notes: (app.state?.annotations ?? []).filter((a) => a.source?.source_id === source.id).length,
      };
    }),
  );
  const here = $derived(entries.filter((e) => e.sections.includes(app.viewingId ?? '')));
  const chapter = $derived(app.chapterOf(app.viewingId));
  const inChapter = $derived(entries.filter((e) => !here.includes(e) && e.sections.some((id) => chapter?.concept_ids.includes(id))));
  const others = $derived(entries.filter((e) => !here.includes(e) && !inChapter.includes(e)));
</script>

<section class="source-list" aria-labelledby="sources-title">
  <h2 id="sources-title">{t("Course sources")}</h2>
  {#if app.source}
    <button class="btn btn-quiet btn-small btn-flush back" onclick={() => (app.sourceList = false)}>← {t("Back to {title}", { title: app.source.title })}</button>
  {/if}
  {#if !entries.length}
    <p class="muted">{t("No documents are registered in this course yet. Add files from Codex.")}</p>
  {/if}
  {#each [
    { title: t("Used in this section"), items: here },
    { title: t("Used elsewhere in this chapter"), items: inChapter },
    { title: here.length || inChapter.length ? t("Other sources") : '', items: others },
  ] as group}
    {#if group.items.length}
      {#if group.title}<h3>{group.title}</h3>{/if}
      <ul>
        {#each group.items as entry (entry.id)}
          <li>
            <button class="open" disabled={!entry.target} onclick={() => entry.target && app.openSource(entry.target)}>
              <span class="name">{entry.name}</span>
              <span class="meta">
                <span class="kind">{entry.kind}</span>
                {#if entry.status === 'failed'}<span class="chip chip-danger">{t("Could not be read")}</span>
                {:else if entry.status === 'needs_review'}<span class="chip chip-caution">{t("Some pages not checked yet")}</span>{/if}
                {#if entry.sections.length}
                  <span>{entry.sections.length === 1 ? app.concept(entry.sections[0])?.title : t("{count} sections", { count: entry.sections.length })}</span>
                {:else}
                  <span>{t("Not used on the route")}</span>
                {/if}
                {#if entry.notes}<span class="mine">✎ {entry.notes}</span>{/if}
              </span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  {/each}
</section>

<style>
  .source-list {
    display: grid;
    gap: 0.6rem;
    align-content: start;
    overflow: auto;
  }

  h2 {
    font-size: var(--step-1);
    font-weight: 600;
  }

  h3 {
    margin-top: 0.6rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .back {
    justify-self: start;
  }

  .muted {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  ul {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .open {
    display: grid;
    gap: 0.2rem;
    width: 100%;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
    color: var(--ink);
    text-align: left;
    cursor: pointer;
  }

  .open:hover:not(:disabled) {
    border-color: var(--accent);
  }

  .open:disabled {
    cursor: not-allowed;
    opacity: 0.7;
  }

  .name {
    font-size: var(--step-0);
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.2rem 0.6rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .kind {
    font-weight: 600;
    letter-spacing: 0.03em;
  }

  .mine {
    color: var(--mine);
    font-weight: 600;
  }
</style>
