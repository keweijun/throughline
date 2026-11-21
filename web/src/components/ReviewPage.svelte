<script lang="ts">
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import { locale } from '../lib/i18n.svelte';
  import { scopeSections, storeScope, storedScope, type ReviewScope as Scope } from '../lib/scope.svelte';
  import type { DrillSession as Session, DrillWay, KeyPoint, Mistake } from '../lib/types';
  import Composer from './Composer.svelte';
  import DrillSession from './DrillSession.svelte';
  import ReviewSet from './ReviewSet.svelte';
  import ReviewScope from './ReviewScope.svelte';
  import StudioHandoff from './StudioHandoff.svelte';
  import KeyPoints from './KeyPoints.svelte';
  import MistakesBook from './MistakesBook.svelte';

  // The Review place (issue #219, ADR 0025): ways of reviewing over one scope. Key points and the mistakes book are read
  // at once, with no model turn; a drill session with the fast teacher runs beside them. Nothing comes due.
  const review = $derived(app.state?.review);
  // Review sets written before drill sessions stay to read.
  const shown = $derived((review?.sets ?? []).filter((s) => s.task_ids.length));
  const sessions = $derived(app.state?.drills ?? []);
  const open = $derived(sessions.find((s) => s.id === app.drillOpen));

  // The scope the learner last chose in this course; everything studied until they choose.
  let scope = $state<Scope>(storedScope());
  $effect(() => {
    void app.state?.course.id;
    scope = storedScope();
  });
  function setScope(value: Scope) {
    scope = value;
    storeScope(value);
  }
  const everything = $derived(!scope.chapter_ids.length && !scope.concept_ids.length);
  const sections = $derived(scopeSections(scope));
  const scoped = $derived(everything ? undefined : { chapter_ids: scope.chapter_ids, concept_ids: scope.concept_ids });

  // The Review place opens on the key points, so it is never empty once something is studied.
  let tab = $state<'points' | 'mistakes'>('points');
  const chapters = $derived(
    app.chapters
      .map((chapter) => ({ chapter, ids: chapter.concept_ids.filter((id) => sections.includes(id) && !!app.keyPoints(id)) }))
      .filter((c) => c.ids.length),
  );
  // Sections whose lesson finished before key points existed get them while the app is idle; a section only practised,
  // with no lesson, has none to sum up.
  const waiting = $derived(sections.filter((id) => !app.keyPoints(id) && app.studied(id)).length);
  const mistakes = $derived((app.state?.mistakes ?? []).filter((m) => m.concept_ids.some((id) => sections.includes(id))));

  const draftKey = 'review-request';
  const request = $derived(app.drafts.get(draftKey));
  let busy = $state(false);

  async function drill(body: Parameters<typeof app.startDrill>[0] = {}) {
    if (busy) return;
    busy = true;
    const result = await app.startDrill(body);
    busy = false;
    return result;
  }

  async function drillFor() {
    const sent = request;
    if (!(await drill({ ...(sent.trim() ? { message: sent } : {}), ...(scoped ? { scope: scoped } : {}) }))) return;
    if (app.drafts.get(draftKey) === sent) app.drafts.set(draftKey, '');
  }

  // A point or a mistake starts a session on just that, in its section.
  function test(point: KeyPoint, conceptId: string) {
    void drill({ message: t("Test me on this key point, in a new situation: {point}", { point: point.statement }), scope: { concept_ids: [conceptId] } });
  }

  function retry(entry: Mistake) {
    const what = entry.idea || entry.part || entry.question;
    void drill({ message: t("I got this wrong before. Ask me about it again, in a new situation: {what}", { what }), scope: { concept_ids: entry.concept_ids } });
  }

  const titles = (ids: string[] = []) => ids.map((id) => app.concept(id)?.title ?? id).join(', ');

  // Ways to review besides quick questions (issue #229): the fast teacher runs some in a session, Studio does the rest.
  const ways: { way: DrillWay; label: MessageKey }[] = [
    { way: 'explain', label: "Explain it back" },
    { way: 'oral', label: "Oral quiz" },
    { way: 'confusable', label: "Tell confusable ideas apart" },
  ];
  const covers = $derived(
    everything
      ? t('everything I have studied in this course')
      : [...scope.chapter_ids.map((id) => t('the chapter "{chapter}"', { chapter: app.chapters.find((c) => c.id === id)?.title ?? id })),
         ...scope.concept_ids.map((id) => t('the section "{section}"', { section: app.concept(id)?.title ?? id }))].join(', '),
  );
  const studioWays = $derived([
    { key: 'mock', label: t("Mock exam"), request: t("Write me a mock exam on {scope}, built from the course's own exercises and any past papers among its sources, in the style of the real exam.", { scope: covers }) },
    { key: 'sheet', label: t("Formula sheet"), request: t("Make me a one-page formula sheet for {scope}: each result with when it holds.", { scope: covers }) },
    { key: 'mistakes', label: t("My mistakes on one page"), request: t("Make me one page on the mistakes I keep making in {scope}, each with the right idea and a quick check.", { scope: covers }) },
  ]);
  const reviewContext = $derived({
    label: t('Review: {scope}', { scope: everything ? t("Everything studied") : titles(sections) }),
    text: `the Review place, covering ${sections.map((id) => `"${app.concept(id)?.title ?? id}" (${id})`).join(', ')}`,
  });
  const chapterTitle = (id?: string) => app.chapters.find((c) => c.id === id)?.title ?? id ?? '';
  function label(session: Session) {
    if (session.kind === 'chapter') return t("Chapter drill · {chapter}", { chapter: chapterTitle(session.chapter_id) });
    if (session.kind === 'warm_up') return t("Warm-up before {section}", { section: titles([session.concept_id!]) });
    const way = ways.find((w) => w.way === session.way);
    const scope = [...(session.scope?.chapter_ids ?? []).map(chapterTitle), titles(session.scope?.concept_ids)].filter(Boolean).join(', ');
    const covered = scope || t("Everything studied");
    return way ? `${t(way.label)} · ${covered}` : covered;
  }
  const when = (at: number) => new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(at * 1000));
</script>

{#if review}
  <article class="place" aria-labelledby="review-title">
    <header class="head">
      <h1 id="review-title">{t("Review")}</h1>
      <p class="intro">{t("Read your key points, go over what you missed, or ask for questions, on everything you have studied or just a part of it.")}</p>
      {#if review.reviewable || sections.length}<ReviewScope value={scope} onchange={setScope} />{/if}
    </header>

    {#if !review.reviewable && !sections.length && !shown.length && !sessions.length}
      <section class="empty">
        <h2>{t("Nothing to review yet")}</h2>
        <p>{t("Once you have studied a section, you can review it here.")}</p>
      </section>
    {:else}
      <div class="columns">
        <div class="reference">
          <div class="tabs" role="tablist" aria-label={t("Ways to review")}>
            <button role="tab" id="tab-points" aria-selected={tab === 'points'} aria-controls="panel-points" onclick={() => (tab = 'points')}>{t("Key points")}</button>
            <button role="tab" id="tab-mistakes" aria-selected={tab === 'mistakes'} aria-controls="panel-mistakes" onclick={() => (tab = 'mistakes')}>{t("Mistakes")}</button>
          </div>
          {#if tab === 'points'}
            <div class="panel" role="tabpanel" id="panel-points" aria-labelledby="tab-points">
              {#each chapters as { chapter, ids } (chapter.id)}
                {@const sheet = app.chapterSheet(chapter.id)}
                <section class="chapter" aria-label={chapter.title}>
                  {#if app.chapters.length > 1}<h2>{chapter.title}</h2>{/if}
                  {#if sheet && ids.length > 1}<div class="prose connection" use:markdown={{ language: locale.language, text: sheet.connection }}></div>{/if}
                  {#each ids as id (id)}
                    <KeyPoints value={app.keyPoints(id)!} section ontest={(point) => test(point, id)} />
                  {/each}
                </section>
              {:else}
                {#if !waiting}<p class="note">{t("Key points appear here once you finish a section's lesson.")}</p>{/if}
              {/each}
              {#if waiting}
                <p class="note">
                  {waiting === 1 ? t("The key points of 1 studied section are still being written.") : t("The key points of {count} studied sections are still being written.", { count: waiting })}
                </p>
              {/if}
            </div>
          {:else}
            <div class="panel" role="tabpanel" id="panel-mistakes" aria-labelledby="tab-mistakes">
              <MistakesBook entries={mistakes} onretry={retry} />
            </div>
          {/if}
        </div>

        <aside class="session" aria-labelledby="drill-title">
          {#if open}
            <header class="session-head">
              <button class="link" onclick={() => (app.drillOpen = null)}>{t("← All sessions")}</button>
              <div class="session-title">
                <h2 id="drill-title">{label(open)}</h2>
                <p class="meta">{when(open.created_at)}</p>
              </div>
            </header>
            <DrillSession session={open} />
          {:else}
            <!-- One box: sent empty, the teacher picks what to ask; with words, the learner says what to drill. -->
            <section class="ask">
              <h2 id="drill-title">{t("Drill")}</h2>
              {#snippet header()}{t("Leave it empty and the teacher picks what to ask")}{/snippet}
              <Composer
                id="review-request"
                value={request}
                onvalue={(value) => app.drafts.set(draftKey, value)}
                label={t("What to review")}
                placeholder={t("For example: the variational method, but not the derivations")}
                submitLabel={request.trim() ? t("Start") : t("Drill me")}
                allowEmpty
                disabled={busy || !review.reviewable}
                onsubmit={drillFor}
                {header}
                preview={false}
              />
              <div class="ways" role="group" aria-label={t("Other ways to review")}>
                <span class="ways-label">{t("Other ways")}</span>
                {#each ways as item (item.way)}
                  <button class="chip-way" disabled={busy || !review.reviewable} onclick={() => drill({ way: item.way, ...(scoped ? { scope: scoped } : {}) })}>{t(item.label)}</button>
                {/each}
              </div>
              <div class="ways studio" role="group" aria-label={t("With Studio")}>
                <span class="ways-label">{t("With Studio")}</span>
                {#each studioWays as item (item.key)}
                  <StudioHandoff variant="chip" place={{ kind: 'review', way: item.key }} label={item.label} request={item.request} context={reviewContext} />
                {/each}
              </div>
            </section>
            {#if sessions.length}
              <section class="sessions" aria-labelledby="sessions-title">
                <h2 id="sessions-title">{t("Earlier sessions")}</h2>
                <ul>
                  {#each sessions as session (session.id)}
                    <li>
                      <button class="open-session" onclick={() => (app.drillOpen = session.id)}>
                        <span class="title">{label(session)}</span>
                        <span class="meta">{when(session.updated_at ?? session.created_at)}{#if session.task_ids.length}&nbsp;· {session.task_ids.length === 1 ? t("1 question") : t("{count} questions", { count: session.task_ids.length })}{/if}</span>
                      </button>
                    </li>
                  {/each}
                </ul>
              </section>
            {/if}
            {#if shown.length}
              <details class="sets">
                <summary>{t("Review sets from before")}</summary>
                {#each shown as value (value.id)}
                  <ReviewSet {value} collapsed />
                {/each}
              </details>
            {/if}
          {/if}
        </aside>
      </div>
    {/if}
  </article>
{/if}

<style>
  /* A place of its own, like the Overview: wide enough for the reference and the questions side by side. */
  .place {
    max-width: calc(var(--measure) + 34rem);
    margin-inline: auto;
    display: grid;
    gap: 2rem;
    container-type: inline-size;
  }

  .head {
    max-width: var(--measure);
  }

  h1 {
    font-family: var(--serif);
    font-size: clamp(var(--step-3), 4.2vw, 2.75rem);
    font-weight: 600;
    line-height: 1.1;
  }

  .intro {
    margin: 0.9rem 0 1.25rem;
    font-family: var(--serif);
    font-size: var(--step-1);
    line-height: 1.45;
    color: var(--ink-soft);
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--pencil);
  }

  /* Reference beside the questions on a wide window, one above the other otherwise. */
  .columns {
    display: grid;
    gap: 2.5rem;
  }

  .reference {
    max-width: var(--measure);
  }

  @container (min-width: 62rem) {
    .columns {
      grid-template-columns: minmax(0, var(--measure)) minmax(24rem, 1fr);
      align-items: start;
    }

    .session {
      position: sticky;
      top: 1rem;
    }
  }

  .reference,
  .panel,
  .chapter {
    display: grid;
    gap: 1.5rem;
  }

  .chapter h2 {
    color: var(--ink);
  }

  .connection {
    margin-top: -0.75rem;
    font-size: var(--step-0);
    line-height: 1.6;
    color: var(--ink-soft);
  }

  .tabs {
    display: flex;
    gap: 1.25rem;
    border-bottom: 1px solid var(--rule);
  }

  [role='tab'] {
    padding: 0 0 0.5rem;
    border: 0;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    background: none;
    color: var(--pencil);
    font: inherit;
    font-weight: 600;
    cursor: pointer;
  }

  [role='tab'][aria-selected='true'] {
    border-bottom-color: var(--accent);
    color: var(--ink);
  }

  .session {
    display: grid;
    gap: 2rem;
  }

  .ask {
    display: grid;
    gap: 0.9rem;
  }


  .sets {
    display: grid;
    gap: 1.5rem;
  }

  .ways {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.35rem 0.75rem;
  }

  .ways-label {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .chip-way {
    padding: 0.2rem 0.7rem;
    border: 1px solid var(--rule-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--ink-soft);
    font-size: var(--step--1);
    cursor: pointer;
  }

  .chip-way:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--accent);
  }

  .sets > summary {
    font-size: var(--step--1);
    color: var(--pencil);
    cursor: pointer;
  }

  .session-head {
    display: grid;
    gap: 0.3rem;
  }

  .session-head h2 {
    color: var(--ink);
  }

  .session-title {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.2rem 1rem;
  }

  .meta {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .link {
    justify-self: start;
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
  }

  .sessions ul {
    display: grid;
    gap: 0.4rem;
    margin: 0.6rem 0 0;
    padding: 0;
    list-style: none;
  }

  .open-session {
    display: grid;
    gap: 0.15rem;
    width: 100%;
    padding: 0.55rem 0.8rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
    color: var(--ink);
    text-align: left;
    cursor: pointer;
  }

  .open-session:hover {
    border-color: var(--accent);
  }

  .open-session .title {
    font-weight: 600;
  }

  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .empty {
    display: grid;
    justify-items: start;
    gap: 0.5rem;
    padding: 1.25rem 1.35rem;
    border: 1px dashed var(--rule-strong);
    border-radius: var(--radius);
    font-size: var(--step-0);
  }
</style>
