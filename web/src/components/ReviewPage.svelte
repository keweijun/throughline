<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import Composer from './Composer.svelte';
  import ReviewSet from './ReviewSet.svelte';

  // Review on request (ADR 0014): nothing comes due; the learner asks for a set of questions whenever they like.
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

  // Chapters with something studied can narrow a request.
  const chapters = $derived((app.state?.curriculum.chapters ?? []).filter((c) => c.concept_ids.some((id) => app.studied(id))));
  let scope = $state<string[]>([]);
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
    const body = { ...(sent.trim() ? { request: sent } : {}), ...(scope.length ? { scope: { chapter_ids: scope } } : {}) };
    if (!(await ask(body))) return;
    if (app.drafts.get(draftKey) === sent) app.drafts.set(draftKey, '');
    scope = [];
  }

  const toggle = (id: string) => (scope = scope.includes(id) ? scope.filter((x) => x !== id) : [...scope, id]);
</script>

{#if review}
  <article class="page" aria-labelledby="review-title">
    <header class="head">
      <h1 id="review-title">{t("Review")}</h1>
      <p class="intro">{t("Answer from memory, without looking back. Ask for questions whenever you like: the teacher picks what you have gone longest without practising and what you missed before, or you say what to review.")}</p>
    </header>

    {#if !review.reviewable && !shown.length}
      <section class="empty">
        <h2>{t("Nothing to review yet")}</h2>
        <p>{t("Once you have studied a section, you can review it here.")}</p>
      </section>
    {:else}
      <section class="ask" aria-labelledby="ask-title">
        <h2 id="ask-title" class="visually-hidden">{t("Ask for review questions")}</h2>
        <button class="btn btn-primary" disabled={busy || !review.reviewable} onclick={() => ask()}>{t("Review for me")}</button>
        {#snippet header()}{t("Or say what to review · the teacher writes questions on what you have studied")}{/snippet}
        {#snippet tools()}
          {#if chapters.length > 1}
            <span class="scope" role="group" aria-label={t("Only these chapters")}>
              {#each chapters as chapter (chapter.id)}
                <button class="chip-toggle" aria-pressed={scope.includes(chapter.id)} onclick={() => toggle(chapter.id)}>{chapter.title}</button>
              {/each}
            </span>
          {/if}
        {/snippet}
        <Composer
          id="review-request"
          value={request}
          onvalue={(value) => app.drafts.set(draftKey, value)}
          label={t("What to review")}
          placeholder={t("For example: the variational method, but not the derivations")}
          submitLabel={t("Ask for questions")}
          disabled={busy}
          allowEmpty={scope.length > 0}
          onsubmit={askFor}
          {header}
          {tools}
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
    {/if}
  </article>
{/if}

<style>
  .page {
    animation: enter-rise var(--settle) var(--ease-out);
    max-width: var(--measure);
    margin-inline: auto;
    display: grid;
    gap: 2rem;
  }

  h1 {
    font-family: var(--serif);
    font-size: clamp(var(--step-3), 4.2vw, 2.75rem);
    font-weight: 600;
    line-height: 1.1;
  }

  .intro {
    margin-top: 0.9rem;
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

  .ask {
    display: grid;
    gap: 0.9rem;
  }

  .ask > .btn {
    justify-self: start;
  }

  .scope {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .chip-toggle {
    padding: 0.15rem 0.6rem;
    border: 1px solid var(--rule-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--ink-soft);
    font-size: var(--step--1);
    cursor: pointer;
  }

  .chip-toggle[aria-pressed='true'] {
    border-color: var(--accent);
    background: var(--accent-wash);
    color: var(--accent);
  }

  .sets {
    display: grid;
    gap: 1.5rem;
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
