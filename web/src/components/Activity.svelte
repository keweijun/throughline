<script lang="ts">
  import { api } from '../lib/api';
  import { locale, t, type MessageKey } from '../lib/i18n.svelte';
  import { dayKey, firstDay, level, summarize, WEEKS, type ActivityKind, type ActivityView, type Day } from '../lib/activity';

  /**
   * Settings → Activity: when the learner studied, across every course, worked out from what the courses record. It
   * shows what happened and nothing to keep up: no streaks, goals or missed days.
   */

  let view = $state<ActivityView | null>(null);
  let failed = $state('');
  let selected = $state<string | null>(null);
  let grid: HTMLDivElement | undefined = $state();

  $effect(() => {
    api
      .get<ActivityView>('/api/activity')
      .then((answer) => (view = answer))
      .catch((error) => (failed = error instanceof Error ? error.message : String(error)));
  });

  const today = new Date();
  const todayKey = dayKey(today);
  const first = firstDay(today);
  const summary = $derived(view ? summarize(view, first) : null);

  // The calendar's days, a column per week from Monday, ending with today.
  const weeks = $derived.by(() => {
    const columns: Date[][] = [];
    const day = new Date(first);
    for (let w = 0; w < WEEKS; w++) {
      const column: Date[] = [];
      for (let d = 0; d < 7; d++) {
        column.push(new Date(day));
        day.setDate(day.getDate() + 1);
      }
      columns.push(column);
    }
    return columns;
  });
  const shown = $derived(summary ? [...summary.days.values()].filter((d) => d.date >= first && d.key <= todayKey) : []);
  const total = $derived(shown.reduce((sum, d) => sum + d.seconds, 0));

  // Opens on today, or on the last day with something in it.
  $effect(() => {
    if (!summary || selected) return;
    const latest = shown.reduce<Day | null>((best, d) => (!best || d.key > best.key ? d : best), null);
    selected = summary.days.has(todayKey) || !latest ? todayKey : latest.key;
  });
  const chosen = $derived(selected ? summary?.days.get(selected) ?? null : null);
  const chosenDate = $derived.by(() => {
    if (!selected) return null;
    const [y, m, d] = selected.split('-').map(Number);
    return new Date(y, m - 1, d);
  });

  function duration(seconds: number) {
    const minutes = Math.max(1, Math.round(seconds / 60));
    if (minutes < 60) return t('{minutes} min', { minutes });
    // Past ten hours, minutes are noise in an estimate.
    if (minutes >= 600) return t('{hours} h', { hours: Math.round(minutes / 60) });
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? t('{hours} h {minutes} min', { hours, minutes: rest }) : t('{hours} h', { hours });
  }
  const about = (seconds: number) => t('about {time}', { time: duration(seconds) });
  const longDate = (date: Date) => new Intl.DateTimeFormat(locale.language, { weekday: 'long', month: 'long', day: 'numeric' }).format(date);
  const shortDate = (date: Date) => new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(date);
  const month = (date: Date) => new Intl.DateTimeFormat(locale.language, { month: 'short' }).format(date);
  const weekday = (date: Date) => new Intl.DateTimeFormat(locale.language, { weekday: 'short' }).format(date);

  function describe(date: Date) {
    const day = summary?.days.get(dayKey(date));
    return `${longDate(date)}: ${day ? about(day.seconds) : t('nothing recorded')}`;
  }

  // A month's name sits over the first week that holds its first day, and over the first week shown.
  function monthLabel(column: Date[], index: number) {
    if (index === 0) return month(column[0]);
    const start = column.find((d) => d.getDate() === 1);
    return start ? month(start) : '';
  }

  // The calendar is one tab stop; the arrow keys move a day (up and down) or a week (left and right).
  async function move(event: KeyboardEvent) {
    const step = { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -7, ArrowRight: 7 }[event.key];
    if (!step || !chosenDate) return;
    event.preventDefault();
    const next = new Date(chosenDate);
    next.setDate(next.getDate() + step);
    if (next < first || dayKey(next) > todayKey) return;
    selected = dayKey(next);
    await Promise.resolve();
    grid?.querySelector<HTMLButtonElement>(`[data-day="${selected}"]`)?.focus();
  }

  const COLUMNS: { kind: ActivityKind; label: MessageKey }[] = [
    { kind: 'step', label: 'Lesson steps' },
    { kind: 'answer', label: 'Answers' },
    { kind: 'question', label: 'Questions' },
    { kind: 'note', label: 'Notes' },
    { kind: 'drill', label: 'Drill messages' },
  ];
</script>

<div class="head">
  <h3>{t('Activity')}</h3>
  {#if failed}
    <p class="lead" role="status">{t('Could not read your activity:')} {failed}</p>
  {:else if !summary}
    <p class="lead" role="status">{t('Reading your courses…')}</p>
  {:else if !shown.length}
    <p class="lead">{t('Nothing yet. Days you study show here.')}</p>
  {:else}
    <p class="lead">
      {shown.length === 1
        ? t('1 day of study in the last six months, {time} in all.', { time: about(total) })
        : t('{days} days of study in the last six months, {time} in all.', { days: shown.length, time: about(total) })}
    </p>
  {/if}
</div>

{#if summary}
  <section class="group" aria-labelledby="group-calendar">
    <div class="label">
      <h4 id="group-calendar">{t('Last six months')}</h4>
      <span class="legend" aria-hidden="true">
        {t('Less')}
        {#each [0, 1, 2, 3, 4] as step (step)}<span class="cell level-{step}"></span>{/each}
        {t('More')}
      </span>
    </div>
    <div class="card calendar">
      <div class="months" aria-hidden="true">
        {#each weeks as column, index (index)}<span>{monthLabel(column, index)}</span>{/each}
      </div>
      <div class="days">
        <div class="weekdays" aria-hidden="true">
          {#each weeks[0] as date, index (index)}<span>{index % 2 === 0 ? weekday(date) : ''}</span>{/each}
        </div>
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <div class="grid" bind:this={grid} role="group" aria-label={t('Days studied')} onkeydown={move}>
          {#each weeks as column, w (w)}
            {#each column as date (dayKey(date))}
              {@const key = dayKey(date)}
              {#if key > todayKey}
                <span class="cell future"></span>
              {:else}
                <button
                  class="cell level-{level(summary.days.get(key)?.seconds ?? 0)}"
                  data-day={key}
                  aria-label={describe(date)}
                  aria-pressed={selected === key}
                  title={describe(date)}
                  tabindex={selected === key ? 0 : -1}
                  onclick={() => (selected = key)}
                ></button>
              {/if}
            {/each}
          {/each}
        </div>
      </div>
    </div>
  </section>

  {#if chosenDate}
    <section class="group" aria-labelledby="group-day">
      <div class="label">
        <h4 id="group-day">{longDate(chosenDate)}</h4>
        <!-- A day in one course shows its time on that course's row. -->
        {#if chosen && chosen.courses.length > 1}<span class="aside">{about(chosen.seconds)}</span>{/if}
      </div>
      <div class="card">
        {#if chosen}
          {#each chosen.courses as course (course.name)}
            <div class="setting">
              <div class="text">
                <span class="title">{course.title}</span>
                <p class="counts">
                  {#each COLUMNS.filter((c) => course.counts[c.kind]) as column (column.kind)}
                    <span>{t(column.label)} <strong>{course.counts[column.kind]}</strong></span>
                  {/each}
                </p>
              </div>
              <span class="aside">{about(course.seconds)}</span>
            </div>
          {/each}
        {:else}
          <p class="empty">{t('Nothing recorded on this day.')}</p>
        {/if}
      </div>
    </section>
  {/if}

  {#if summary.courses.length}
    <section class="group" aria-labelledby="group-courses">
      <div class="label"><h4 id="group-courses">{t('Courses')}</h4></div>
      <div class="card">
        {#each summary.courses as course (course.name)}
          <div class="setting">
            <div class="text">
              <span class="title">{course.title}</span>
              <p>{t('Last studied {date}', { date: shortDate(new Date(course.last * 1000)) })}</p>
            </div>
            <span class="aside">{course.seconds ? about(course.seconds) : t('Not in the last six months')}</span>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <p class="foot">
    {t('Worked out from what your courses record. Time is an estimate: things you did less than 20 minutes apart count as one sitting.')}
  </p>
{/if}

<style>
  .legend {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .legend .cell {
    width: 0.7rem;
    height: 0.7rem;
  }

  .calendar {
    padding: 0.875rem 1rem 1rem;
  }

  .months,
  .grid {
    display: grid;
    grid-template-columns: repeat(26, minmax(0, 1fr));
    column-gap: 3px;
  }

  .months {
    margin-inline-start: 2.25rem;
    margin-bottom: 0.3rem;
    font-size: 0.72rem;
    color: var(--pencil);
    white-space: nowrap;
  }

  /* A label may run over the next weeks' columns; it never needs more than a month's worth. */
  .months span {
    min-width: 0;
    overflow: visible;
  }

  .days {
    display: grid;
    grid-template-columns: 2.25rem minmax(0, 1fr);
  }

  .weekdays {
    display: grid;
    grid-template-rows: repeat(7, 1fr);
    row-gap: 3px;
    font-size: 0.72rem;
    color: var(--pencil);
    align-items: center;
  }

  .grid {
    grid-template-rows: repeat(7, auto);
    grid-auto-flow: column;
    row-gap: 3px;
  }

  .cell {
    display: block;
    aspect-ratio: 1;
    width: 100%;
    padding: 0;
    border: 0;
    border-radius: 3px;
    background: color-mix(in srgb, var(--ink) 7%, transparent);
  }

  button.cell {
    cursor: pointer;
  }

  button.cell:hover {
    box-shadow: 0 0 0 1px var(--rule-strong);
  }

  /* One hue, light to dark: more time studied is a deeper square. */
  .level-1 {
    background: color-mix(in srgb, var(--accent) 25%, var(--raised));
  }

  .level-2 {
    background: color-mix(in srgb, var(--accent) 48%, var(--raised));
  }

  .level-3 {
    background: color-mix(in srgb, var(--accent) 72%, var(--raised));
  }

  .level-4 {
    background: var(--accent);
  }

  .cell.future {
    background: none;
  }

  button.cell[aria-pressed='true'] {
    outline: 2px solid var(--ink);
    outline-offset: 1px;
  }

  button.cell:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .aside {
    font-size: var(--step--1);
    color: var(--pencil);
    white-space: nowrap;
  }

  .counts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.15rem 0.9rem;
  }

  .counts strong {
    color: var(--ink);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .empty {
    padding: 0.875rem 1rem;
    color: var(--pencil);
    font-size: var(--step--1);
  }
</style>
