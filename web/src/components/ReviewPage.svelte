<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import { locale } from '../lib/i18n.svelte';
  import { scopeSections, storeScope, storedScope, type ReviewScope as Scope } from '../lib/scope.svelte';
  import type { KeyPoint, Mistake } from '../lib/types';
  import Composer from './Composer.svelte';
  import ReviewSet from './ReviewSet.svelte';
  import ReviewScope from './ReviewScope.svelte';
  import KeyPoints from './KeyPoints.svelte';
  import MistakesBook from './MistakesBook.svelte';

  // The Review place (issue #219): ways of reviewing over one scope. Key points and the mistakes book are read at once,
  // with no model turn; questions are asked for beside them. Nothing comes due (ADR 0014).
  const review = $derived(app.state?.review);
  const jobs = $derived(review?.jobs ?? []);
  // A set with no questions is shown while they are written or after writing failed, until it is closed.
  const shown = $derived(
    (review?.sets ?? []).filter((s) => s.task_ids.length || (!s.closed_at && jobs.some((j) => j.set_id === s.id))),
  );
  // A set stays current, so its last feedback can be read, until it is closed or a day old once answered.
  const now = Date.now() / 1000;
  const current = $derived(shown.filter((s) => !s.closed_at && (s.open || !s.task_ids.length || now - s.created_at < 86400)));
  const earlier = $derived(shown.filter((s) => !current.includes(s)));

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

  async function ask(body: Parameters<typeof app.askReview>[0] = {}) {
    if (busy) return;
    busy = true;
    const result = await app.askReview(body);
    busy = false;
    return result;
  }

  async function askFor() {
    const sent = request;
    if (!(await ask({ ...(sent.trim() ? { request: sent } : {}), ...(scoped ? { scope: scoped } : {}) }))) return;
    if (app.drafts.get(draftKey) === sent) app.drafts.set(draftKey, '');
  }

  // A point or a mistake asks for questions on just that, in its section.
  function test(point: KeyPoint, conceptId: string) {
    void ask({ request: t("Test me on this key point, in a new situation: {point}", { point: point.statement }), scope: { concept_ids: [conceptId] } });
  }

  function retry(entry: Mistake) {
    const what = entry.idea || entry.part || entry.question;
    void ask({ request: t("I got this wrong before. Ask me about it again, in a new situation: {what}", { what }), scope: { concept_ids: entry.concept_ids } });
  }
</script>

{#if review}
  <article class="place" aria-labelledby="review-title">
    <header class="head">
      <h1 id="review-title">{t("Review")}</h1>
      <p class="intro">{t("Read your key points, go over what you missed, or ask for questions, on everything you have studied or just a part of it.")}</p>
      {#if review.reviewable || sections.length}<ReviewScope value={scope} onchange={setScope} />{/if}
    </header>

    {#if !review.reviewable && !sections.length && !shown.length}
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

        <aside class="session" aria-labelledby="ask-title">
          <section class="ask">
            <h2 id="ask-title">{t("Review questions")}</h2>
            <button class="btn btn-primary" disabled={busy || !review.reviewable} onclick={() => ask(scoped ? { scope: scoped } : {})}>{t("Review for me")}</button>
            {#snippet header()}{t("Or say what to review · the teacher writes questions on what you have studied")}{/snippet}
            <Composer
              id="review-request"
              value={request}
              onvalue={(value) => app.drafts.set(draftKey, value)}
              label={t("What to review")}
              placeholder={t("For example: the variational method, but not the derivations")}
              submitLabel={t("Ask for questions")}
              disabled={busy}
              allowEmpty={!!scoped}
              onsubmit={askFor}
              {header}
              preview={false}
            />
          </section>
          {#if current.length}
            <section class="sets" aria-labelledby="open-title">
              <h2 id="open-title">{t("Current")}</h2>
              {#each current as value (value.id)}
                <ReviewSet {value} />
              {/each}
            </section>
          {/if}
          {#if earlier.length}
            <section class="sets" aria-labelledby="earlier-title">
              <h2 id="earlier-title">{t("Earlier")}</h2>
              {#each earlier as value (value.id)}
                <ReviewSet {value} collapsed />
              {/each}
            </section>
          {/if}
        </aside>
      </div>
    {/if}
  </article>
{/if}

<style>
  /* A place of its own, like the Overview: wide enough for the reference and the questions side by side. */
  .place {
    max-width: calc(var(--measure) + 28rem);
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
      grid-template-columns: minmax(0, var(--measure)) minmax(22rem, 1fr);
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

  .ask > .btn {
    justify-self: start;
  }

  .sets {
    display: grid;
    gap: 1.5rem;
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
