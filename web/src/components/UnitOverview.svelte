<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { labelFor } from '../lib/markdown';
  import { verification } from '../lib/format';
  import type { Preview } from '../lib/types';

  let { preview }: { preview: Preview } = $props();

  const o = $derived(preview.overview);
  const next = $derived(app.concept(preview.next_concept_id));
  const chapter = $derived(app.chapterOf(preview.concept.id));
  const opensChapter = $derived(chapter?.concept_ids[0] === preview.concept.id);
  const sourceTitle = (id: string) => app.state?.sources.find((s) => s.id === id)?.path.split(/[\\/]/).pop() ?? id;
</script>

<div class="overview">
  {#if o.origin === 'teacher'}
    <p class="problem">{o.core_problem}</p>
    <ol class="steps">
      {#each o.steps as step}
        <li>{step}</li>
      {/each}
    </ol>
    <dl>
      <div><dt>{t("Connections")}</dt><dd>{o.prior}; {o.next}</dd></div>
      <div><dt>{t("Afterwards you can")}</dt><dd>{o.target_ability}</dd></div>
    </dl>
  {:else}
    <p class="note">
      {#if chapter && !opensChapter}
        {t("Part of the chapter {chapter}. Its overview opens the chapter's first section.", { chapter: chapter.title })}
      {:else}
        {app.hasLesson(preview.concept.id)
          ? t("The teacher's chapter overview is at the start of the first lesson below.")
          : t("The first lesson opens with an overview of the whole chapter, written by the teacher.")}
      {/if}
    </p>
    <!-- Only what the plan says; an empty row would tell the learner nothing. -->
    {#if preview.prerequisites.length || next}
      <dl>
        {#if preview.prerequisites.length}
          <div><dt>{t("Builds on")}</dt><dd>{preview.prerequisites.map((p) => p.title).join(', ')}</dd></div>
        {/if}
        {#if next}<div><dt>{t("Up next")}</dt><dd>{next.title}</dd></div>{/if}
      </dl>
    {/if}
  {/if}

  <div class="sources">
    <h3>{t("Sources")}</h3>
    {#if preview.sources.length}
      <ul>
        {#each preview.sources as ref}
          {@const v = verification(ref.verification)}
          <li>
            <button class="btn btn-quiet btn-small" onclick={() => app.openSource(ref)}>
              {sourceTitle(ref.source_id)}, {labelFor(ref)}
            </button>
            <span class="chip chip-{v.tone}">{t(v.label)}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="note">{t("No source pages are linked to this section yet.")}</p>
    {/if}
  </div>

  {#if preview.set_aside?.length}
    <div class="sources">
      <h3>{t("Set aside for now")}</h3>
      <p class="note">{t("Material for this section that the course plan left out of the lessons for now. It stays on the route for later review.")}</p>
      <ul>
        {#each preview.set_aside as ref}
          <li>
            <button class="btn btn-quiet btn-small" onclick={() => app.openSource(ref)}>
              {sourceTitle(ref.source_id)}, {labelFor(ref)}
            </button>
            <span class="chip chip-caution">{ref.disposition === 'deferred' ? t("Deferred") : t("Not checked yet")}</span>
            {#if ref.reason}<span class="reason">{ref.reason}</span>{/if}
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</div>

<style>
  .overview {
    display: grid;
    gap: 1rem;
    font-size: var(--step-0);
  }

  .problem {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-style: italic;
    line-height: 1.45;
    color: var(--ink);
  }

  .steps {
    margin: 0;
    padding-left: 1.3rem;
    display: grid;
    gap: 0.3rem;
  }

  dl {
    display: grid;
    gap: 0.6rem;
    margin: 0;
  }

  dt {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  dd {
    margin: 0.1rem 0 0;
  }

  .note {
    color: var(--pencil);
  }

  .sources {
    padding-top: 0.8rem;
    border-top: 1px solid var(--rule);
  }

  h3 {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
    margin-bottom: 0.35rem;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 0.2rem;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  li .btn {
    padding-left: 0;
    white-space: normal;
    text-align: left;
  }

  .reason {
    flex-basis: 100%;
    color: var(--pencil);
    font-size: var(--step--1);
  }
</style>
