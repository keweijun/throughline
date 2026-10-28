<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';
  import CodexLink from './CodexLink.svelte';
  import ChapterBuild from './ChapterBuild.svelte';
  import ChapterRecap from './ChapterRecap.svelte';
  import ChapterQuiz from './ChapterQuiz.svelte';

  let { chapterId }: { chapterId: string } = $props();

  const chapters = $derived(app.chapters);
  const number = $derived(chapters.findIndex((c) => c.id === chapterId));
  const chapter = $derived(chapters[number]);
  const ids = $derived(chapter?.concept_ids ?? []);
  const route = $derived(app.state?.curriculum.route ?? []);
  const isCurrent = $derived(!!app.currentId && ids.includes(app.currentId));
  const last = $derived(ids.at(-1));
  const following = $derived(last ? app.concept(route[route.indexOf(last) + 1]) : undefined);
  const course = $derived(app.libraryCourse);

  function stateOf(id: string) {
    if (id === app.currentId) return { label: t("You are here"), tone: 'accent' };
    if (app.isSkipped(id)) return { label: t("Skipped"), tone: 'caution' };
    if (app.studied(id)) return { label: t("Studied"), tone: 'good' };
    if (app.hasLesson(id)) return { label: t("In progress"), tone: 'plain' };
    // The same word the route uses for a lesson written ahead in the background.
    if ((app.state?.preparation.jobs ?? []).some((j) => j.concept_id === id && j.status === 'ready')) return { label: t("Lesson ready"), tone: 'plain' };
    return { label: t("Not started"), tone: 'plain' };
  }

  const rows = $derived(
    ids.map((id) => {
      const tasks = app.tasks(id).filter((task) => task.status !== 'skipped');
      return {
        id,
        title: app.concept(id)?.title ?? id,
        state: stateOf(id),
        exercises: { solved: tasks.filter(solved).length, total: tasks.length },
        questions: (app.state?.questions ?? []).filter((q) => q.restore_point?.concept_id === id).length,
        saved: app.explanationsFor(id).filter((e) => e.status === 'pending').length,
      };
    }),
  );

  // What the course plan links to this chapter: a location may serve several sections, so count each once.
  const coverage = $derived.by(() => {
    const entries = (app.state?.curriculum.coverage ?? []).filter((e) => e.concept_ids?.some((id) => ids.includes(id)));
    const links = new Set(ids.flatMap((id) => app.concept(id)?.links ?? []).map((r) => `${r.source_id}/${r.revision}/${r.unit_id}`));
    const mapped = entries.filter((e) => e.disposition === 'mapped');
    return {
      linked: new Set([...links, ...mapped.map((e) => `${e.source_id}/${e.revision}/${e.unit_id}`)]).size,
      verified: mapped.filter((e) => e.verification === 'verified').length,
      deferred: entries.filter((e) => e.disposition === 'deferred').length,
      review: entries.filter((e) => e.disposition === 'needs_review').length,
    };
  });

  // Later sections that list a prerequisite in this chapter; skipping leaves them without it.
  const dependents = $derived(
    route
      .slice(last ? route.indexOf(last) + 1 : route.length)
      .map((id) => app.concept(id))
      .filter((c) => c?.prerequisites?.some((p) => ids.includes(p))),
  );

  function skip() {
    const warning = dependents.length
      ? t("Later sections build on this chapter: {titles}. Skip it anyway? Its sections stay on the route, marked as skipped.", {
          titles: dependents.map((c) => c!.title).join(', '),
        })
      : t("Skip to the next chapter? This chapter's remaining sections stay on the route, marked as skipped.");
    if (confirm(warning)) void app.skipChapter(chapterId);
  }
</script>

{#if chapter}
  <article class="page" aria-labelledby="chapter-title">
    <header class="head">
      <p class="eyebrow">{t("Chapter {number} of {total}", { number: number + 1, total: chapters.length })}</p>
      <h1 id="chapter-title">{chapter.title}</h1>
      {#if chapter.summary}<p class="summary">{chapter.summary}</p>{/if}
      {#if !isCurrent && app.currentId}
        <button class="btn btn-small back" onclick={() => app.view(app.currentId!)}>{t("Back to current section")}</button>
      {/if}
    </header>

    {#if !ids.length}
      <section class="unbuilt">
        <h2>{t("This chapter is not built yet")}</h2>
        <ChapterBuild {chapter} />
      </section>
    {:else}
      <section aria-labelledby="sections-title">
        <h2 id="sections-title">{t("Sections")}</h2>
        <ol class="sections">
          {#each rows as row (row.id)}
            <li>
              <button class="open" onclick={() => app.view(row.id)}>
                <span class="title">{row.title}</span>
                <span class="meta">
                  <span class="chip chip-{row.state.tone}">{row.state.label}</span>
                  {#if row.exercises.total}<span>{t("{solved}/{total} exercises solved", row.exercises)}</span>{/if}
                  {#if row.questions}<span>{row.questions === 1 ? t("1 side question") : t("{count} side questions", { count: row.questions })}</span>{/if}
                  {#if row.saved}<span class="saved">{row.saved === 1 ? t("1 saved question") : t("{count} saved questions", { count: row.saved })}</span>{/if}
                </span>
              </button>
            </li>
          {/each}
        </ol>
      </section>

      <section class="coverage" aria-labelledby="coverage-title">
        <h2 id="coverage-title">{t("Source coverage")}</h2>
        <p>
          {t("{verified} of {linked} linked source locations checked against the original.", coverage)}
          {#if coverage.deferred}{t("Set aside for later: {count}.", { count: coverage.deferred })}{/if}
          {#if coverage.review}<strong>{t("Still to check: {count}.", { count: coverage.review })}</strong>{/if}
        </p>
        <p class="note">{t("From the course plan. A linked location is not a promise that every formula on it was taught.")}</p>
        {#if coverage.review && course}
          <CodexLink prompt={t('$throughline review the pages that still need review in the chapter "{chapter}" of the course {course}', { chapter: chapter.title, course: course.name })}>
            {t("Check this chapter's source locations in Codex")}
          </CodexLink>
        {/if}
      </section>

      {#if app.chapterStudied(chapterId)}
        <ChapterRecap {chapter} />
        <ChapterQuiz {chapter} />
      {:else}
        <p class="note">{t("A recap and a quiz on this chapter open once you have studied one of its sections.")}</p>
      {/if}

      {#if isCurrent && following && app.chapterOf(following.id)?.id !== chapterId}
        <section class="actions" aria-label={t("Chapter actions")}>
          <div>
            <button class="btn" onclick={skip}>{t("Skip to the next chapter")}</button>
            <p class="note">{t("Skipped sections stay on the route. You can come back and study them at any time.")}</p>
          </div>
        </section>
      {/if}
    {/if}
  </article>
{/if}

<style>
  .page {
    max-width: var(--measure);
    margin-inline: auto;
    display: grid;
    gap: 2rem;
  }

  .eyebrow {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  h1 {
    margin-top: 0.35rem;
    font-family: var(--serif);
    font-size: clamp(var(--step-3), 4.2vw, 2.75rem);
    font-weight: 600;
    line-height: 1.1;
    text-wrap: balance;
  }

  .summary {
    margin-top: 0.9rem;
    font-family: var(--serif);
    font-size: var(--step-1);
    line-height: 1.45;
    color: var(--ink-soft);
  }

  .back {
    margin-top: 1rem;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
    margin-bottom: 0.6rem;
  }

  .sections {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
    counter-reset: section;
  }

  .open {
    display: grid;
    gap: 0.3rem;
    width: 100%;
    padding: 0.65rem 0.85rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
    color: var(--ink);
    text-align: left;
    cursor: pointer;
  }

  .open:hover {
    border-color: var(--accent);
  }

  .title {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .title::before {
    counter-increment: section;
    content: counter(section) '. ';
    color: var(--pencil);
    font-weight: 400;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.2rem 0.7rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .meta .saved {
    color: var(--accent);
  }

  .coverage p {
    font-size: var(--step-0);
  }

  .note {
    margin-top: 0.25rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .coverage :global(a) {
    display: inline-block;
    margin-top: 0.5rem;
    font-size: var(--step--1);
  }

  .unbuilt {
    display: grid;
    justify-items: start;
    gap: 0.75rem;
    padding: 1.25rem 1.35rem;
    border: 1px dashed var(--rule-strong);
    border-radius: var(--radius);
  }

  .actions {
    display: grid;
    gap: 1rem;
    padding: 1.25rem 1.35rem;
    border-radius: var(--radius);
    background: var(--accent-wash);
  }
</style>
