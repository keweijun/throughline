<script lang="ts">
  import { t, locale, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import Exercise from './Exercise.svelte';
  import type { ReviewSection } from '../lib/types';

  const review = $derived(app.state?.review);
  const tasks = $derived(review?.tasks ?? []);
  const jobs = $derived(review?.jobs ?? []);
  let busy = $state<string | null>(null);

  const date = (seconds: number) => new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(seconds * 1000));
  const midnight = $derived.by(() => {
    const day = new Date((review?.now ?? Date.now() / 1000) * 1000);
    day.setHours(0, 0, 0, 0);
    return day.getTime() / 1000;
  });

  const preparing = (id: string) => jobs.some((j) => j.concept_id === id && app.isRunning(j.id));
  // The newest request for a section's question, when it ended without one.
  function problem(id: string) {
    const last = jobs.filter((j) => j.concept_id === id).sort((a, b) => (app.turn(a.id)?.started_at ?? 0) - (app.turn(b.id)?.started_at ?? 0)).at(-1);
    if (!last) return null;
    const turn = app.turn(last.id);
    if (last.error) return diagnostic(last.error);
    if (!last.processed && turn && turn.status !== 'running' && turn.status !== 'completed') return t("Preparing the question stopped before it finished.");
    return null;
  }

  // Review questions answered today stay on the page so their feedback can be read and a retry made.
  const answeredToday = $derived(
    tasks.filter(
      (task) =>
        task.history.some((h) => h.action === 'assess') &&
        !review?.due.some((s) => s.task_id === task.id) &&
        (app.turn(task.id.split(':')[0])?.started_at ?? 0) >= midnight,
    ),
  );

  function chapterTitle(id: string) {
    return app.chapterOf(id)?.title;
  }

  function when(section: ReviewSection) {
    return t("Due since {date}", { date: date(section.due_at) });
  }

  async function run(id: string, action: (id: string) => Promise<unknown>) {
    if (busy) return;
    busy = id;
    await action(id);
    busy = null;
  }
</script>

{#if review}
  <article class="page" aria-labelledby="review-title">
    <header class="head">
      <p class="eyebrow">{t("Spaced review")}</p>
      <h1 id="review-title">{t("Review")}</h1>
      <p class="intro">{t("Answer from memory, without looking back. Each section returns after 1, 3, 7, 21 and then 60 days; answering on your own moves it to the next interval, and a review that needs another try starts it over.")}</p>
      {#if app.currentId}
        <button class="btn btn-small back" onclick={() => app.view(app.currentId!)}>{t("Back to current section")}</button>
      {/if}
    </header>

    {#if !review.reviewable && !tasks.length}
      <section class="empty">
        <h2>{t("Nothing to review yet")}</h2>
        <p>{t("A section becomes reviewable once you solve one of its exercises, on your own or with help. It comes back here a day later with a fresh question.")}</p>
      </section>
    {:else}
      {#if review.due.length}
        <section aria-labelledby="due-title">
          <h2 id="due-title">{t("Due today")}</h2>
          <ol class="due">
            {#each review.due as section (section.concept_id)}
              {@const task = tasks.find((x) => x.id === section.task_id)}
              <li class="item" aria-label={app.concept(section.concept_id)?.title ?? section.concept_id}>
                <div class="item-head">
                  <div>
                    <p class="title">{app.concept(section.concept_id)?.title ?? section.concept_id}</p>
                    <p class="meta">
                      {#if chapterTitle(section.concept_id)}<span>{chapterTitle(section.concept_id)}</span>{/if}
                      <span>{when(section)}</span>
                    </p>
                  </div>
                  {#if !task && !preparing(section.concept_id)}
                    <div class="item-actions">
                      <button class="btn btn-primary btn-small" disabled={!!busy} onclick={() => run(section.concept_id, (id) => app.startReview(id))}>{t("Start review")}</button>
                      <button class="btn btn-quiet btn-small" disabled={!!busy} onclick={() => run(section.concept_id, (id) => app.postponeReview(id))}>{t("Not now")}</button>
                    </div>
                  {/if}
                </div>
                {#if task}
                  <Exercise {task} />
                {:else if preparing(section.concept_id)}
                  <p class="status"><span class="chip"><span class="live-dot"></span>{t("Preparing a review question")}</span></p>
                {:else if problem(section.concept_id)}
                  <p class="problem">{t("The review question could not be prepared:")} {problem(section.concept_id)}</p>
                {/if}
              </li>
            {/each}
          </ol>
        </section>
      {:else}
        <section class="caught-up">
          <h2>{t("Nothing due today")}</h2>
          {#if review.next_due_at}
            <p>{t("Next review: {date}.", { date: date(review.next_due_at) })}</p>
          {/if}
        </section>
      {/if}

      {#if review.waiting || review.upcoming}
        <div class="summary">
          {#if review.waiting}<p>{t("{count} more due, waiting for later days: at most {cap} reviews a day, so a break does not pile up.", { count: review.waiting, cap: review.cap })}</p>{/if}
          {#if review.upcoming}<p>{review.upcoming === 1 ? t("1 section is scheduled for a later review.") : t("{count} sections are scheduled for a later review.", { count: review.upcoming })}</p>{/if}
        </div>
      {/if}

      {#if answeredToday.length}
        <section aria-labelledby="done-title">
          <h2 id="done-title">{t("Reviewed today")}</h2>
          <div class="done">
            {#each answeredToday as task (task.id)}
              <Exercise {task} showSection />
            {/each}
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
  }

  .intro {
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

  .due {
    display: grid;
    gap: 1rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .item {
    display: grid;
    gap: 0.85rem;
    padding: 0.9rem 1rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
  }

  .item-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 1rem;
  }

  .title {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem 0.7rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .item-actions {
    display: flex;
    gap: 0.4rem;
  }

  .empty,
  .caught-up {
    display: grid;
    justify-items: start;
    gap: 0.5rem;
    padding: 1.25rem 1.35rem;
    border: 1px dashed var(--rule-strong);
    border-radius: var(--radius);
    font-size: var(--step-0);
  }

  .summary {
    display: grid;
    gap: 0.25rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .done {
    display: grid;
    gap: 1rem;
  }

  .problem {
    color: var(--danger);
    font-size: var(--step-0);
  }
</style>
