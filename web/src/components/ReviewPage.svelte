<script lang="ts">
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import { locale } from '../lib/i18n.svelte';
  import { ago } from '../lib/format';
  import { coverPattern, WIDTH as COVER_WIDTH, HEIGHT as COVER_HEIGHT } from '../lib/covers';
  import { scopeSections, storeScope, storedScope, type ReviewScope as Scope } from '../lib/scope.svelte';
  import type { DrillSession as Session, DrillWay, KeyPoint, Mistake } from '../lib/types';
  import Composer from './Composer.svelte';
  import DrillSession from './DrillSession.svelte';
  import ReviewSet from './ReviewSet.svelte';
  import ReviewScope from './ReviewScope.svelte';
  import StudioHandoff from './StudioHandoff.svelte';
  import SheetView from './SheetView.svelte';
  import KeyPoints from './KeyPoints.svelte';
  import MistakesBook from './MistakesBook.svelte';

  // The Review place (ADR 0014, ADR 0025). It opens on its home: what to go over, with the drill box, then a way into
  // each thing there is to read and the drill sessions, with nothing beside it. What they open takes the page at reading
  // width, laid out as the Studio place is, with a column beside it to move between them and back home. Key points and
  // the mistakes book are read at once, with no model turn; a drill session with the fast teacher takes the page while
  // it is open. Nothing comes due.
  const review = $derived(app.state?.review);
  // Review sets written before drill sessions stay to read.
  const shown = $derived((review?.sets ?? []).filter((s) => s.task_ids.length));
  const sessions = $derived(app.state?.drills ?? []);
  const open = $derived(sessions.find((s) => s.id === app.drillOpen));
  const sheets = $derived(app.state?.sheets ?? []);
  const shownSheet = $derived(sheets.find((s) => s.id === app.sheetOpen) ?? sheets[0]);
  // What the page shows: an open session, else the view chosen, else the home.
  const view = $derived.by(() => {
    if (open) return 'session';
    const tab = app.reviewTab;
    if ((tab === 'sheets' && !shownSheet) || (tab === 'sets' && !shown.length)) return 'home';
    return tab;
  });

  // Another course's Review, reopened where the learner was in it (App.svelte), starts at its home.
  $effect(() => {
    const id = app.state?.course.id;
    if (!id) return;
    if (app.reviewFor && app.reviewFor !== id) {
      app.drillOpen = app.sheetOpen = null;
      app.reviewTab = 'home';
    }
    app.reviewFor = id;
  });

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
  // How the drill asks, chosen in the box: quick questions, or one of the other ways the fast teacher runs.
  let way = $state<DrillWay>('questions');

  async function drill(body: Parameters<typeof app.startDrill>[0] = {}) {
    if (busy) return;
    busy = true;
    const result = await app.startDrill(body);
    busy = false;
    return result;
  }

  async function drillFor() {
    const sent = request;
    const how = way === 'questions' ? {} : { way };
    if (!(await drill({ ...how, ...(sent.trim() ? { message: sent } : {}), ...(scoped ? { scope: scoped } : {}) }))) return;
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

  // How a drill can ask (issue #229): the fast teacher runs these; what Studio makes is a hand-off.
  const ways: { way: DrillWay; label: MessageKey }[] = [
    { way: 'questions', label: "Quick questions" },
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
    { key: 'mock', label: t("a mock exam"), request: t("Write me a mock exam on {scope}, built from the course's own exercises and any past papers among its sources, in the style of the real exam.", { scope: covers }) },
    { key: 'sheet', label: t("a formula sheet"), request: t("Make me a one-page formula sheet for {scope}: each result with when it holds.", { scope: covers }) },
    { key: 'mistakes', label: t("my mistakes on one page"), request: t("Make me one page on the mistakes I keep making in {scope}, each with the right idea and a quick check.", { scope: covers }) },
  ]);
  const reviewContext = $derived({
    label: t('Review: {scope}', { scope: everything ? t("Everything studied") : titles(sections) }),
    text: `the Review place, covering ${sections.map((id) => `"${app.concept(id)?.title ?? id}" (${id})`).join(', ')}`,
  });
  const chapterTitle = (id?: string) => app.chapters.find((c) => c.id === id)?.title ?? id ?? '';
  const sessionScope = (session: Session) =>
    [...(session.scope?.chapter_ids ?? []).map(chapterTitle), titles(session.scope?.concept_ids)].filter(Boolean).join(', ') || t("Everything studied");
  function label(session: Session) {
    if (session.title) return session.title;
    if (session.kind === 'chapter') return t("Chapter drill · {chapter}", { chapter: chapterTitle(session.chapter_id) });
    if (session.kind === 'warm_up') return t("Warm-up before {section}", { section: titles([session.concept_id!]) });
    // Named by how it asks and what it covers, so a session reads as one, not as a chapter's name.
    const asked = ways.find((w) => w.way === session.way && w.way !== 'questions');
    return `${t(asked?.label ?? "Drill")} · ${sessionScope(session)}`;
  }
  const questions = (session: Session) =>
    session.task_ids.length === 1 ? t("1 question") : t("{count} questions", { count: session.task_ids.length });
  const when = (at: number) => new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(at * 1000));
  let now = $state(Date.now());
  $effect(() => {
    const clock = setInterval(() => (now = Date.now()), 60_000);
    return () => clearInterval(clock);
  });

  function openSession(id: string) {
    app.drillOpen = id;
    document.getElementById('stage')?.scrollTo({ top: 0 });
  }

  // The home's ways in show a glimpse of what they open: two points from the section whose points are newest, the
  // latest miss, the top of a sheet.
  const glimpse = $derived.by(() => {
    const newest = sections.map((id) => app.keyPoints(id)).filter((x) => !!x).sort((a, b) => b!.written_at - a!.written_at)[0];
    return newest ? newest.points.slice(0, 2).map((p) => p.statement).join('\n\n') : '';
  });
  const pointChapters = $derived(chapters.map((c) => c.chapter.title).join(' · '));
  const latestMiss = $derived(mistakes.find((m) => !m.right_at));
  let allSessions = $state(false);
  // The course's own lines, as on its cover (ADR 0027), behind the home's question.
  const marks = $derived(app.libraryCourse ? coverPattern(app.libraryCourse.cover?.pattern, app.libraryCourse.name) : []);

  const nothing = $derived(!review?.reviewable && !sections.length && !shown.length && !sessions.length && !sheets.length);
</script>

{#snippet item(current: boolean, onclick: () => void, name: string, aside = '')}
  <li>
    <button class="item" aria-current={current ? 'page' : undefined} {onclick}>
      <span class="name">{name}</span>
      {#if aside}<span class="when">{aside}</span>{/if}
    </button>
  </li>
{/snippet}

{#snippet how()}
  <div class="how" role="radiogroup" aria-label={t("How to drill")}>
    {#each ways as item (item.way)}
      <button type="button" role="radio" aria-checked={way === item.way} onclick={() => (way = item.way)}>{t(item.label)}</button>
    {/each}
  </div>
{/snippet}

{#if review}
  <article class="page still" aria-labelledby="review-title">
    <!-- The top bar already says Review; the heading names the place for assistive technology. -->
    <h1 id="review-title" class="visually-hidden">{t("Review")}</h1>
    {#if nothing}
      <section class="empty">
        <h2>{t("Nothing to review yet")}</h2>
        <p>{t("Once you have studied a section, you can review it here.")}</p>
      </section>
    {:else if view === 'home'}
      <!-- Review's home: what to go over, then the ways into the rest. Sent empty, the box lets the teacher pick what to
           ask; with words, the learner says what to drill. What Studio would make is a line of links, since it leaves
           Review. -->
      <section class="home" aria-labelledby="drill-title">
        <div class="lines" aria-hidden="true">
          <svg viewBox="0 0 {COVER_WIDTH} {COVER_HEIGHT}" preserveAspectRatio="xMidYMid slice">
            {#each marks as mark}<path d={mark.d} class={mark.tone} class:dot={mark.dot} class:wide={mark.wide} />{/each}
          </svg>
        </div>
        <header class="home-head">
          <h2 class="question" id="drill-title">{t("What shall we")} <mark class="swipe">{t("go over?")}</mark></h2>
          <ReviewScope value={scope} onchange={setScope} />
        </header>
        <Composer
          id="review-request"
          value={request}
          onvalue={(value) => app.drafts.set(draftKey, value)}
          label={t("What to review")}
          placeholder={t("What to drill, or leave it empty and the teacher picks")}
          submitLabel={request.trim() ? t("Start") : t("Drill me")}
          allowEmpty
          disabled={busy || !review.reviewable}
          onsubmit={drillFor}
          tools={how}
          preview={false}
        />
        <div class="studio-ways">
          <span>{t("Or have Studio make")}</span>
          <ul aria-label={t("With Studio")}>
            {#each studioWays as item (item.key)}
              <li><StudioHandoff variant="link" place={{ kind: 'review', way: item.key }} label={item.label} request={item.request} context={reviewContext} /></li>
            {/each}
          </ul>
        </div>

        <section class="ways-in" aria-labelledby="home-read">
          <h3 id="home-read">{t("Read")}</h3>
          <ul class="tiles">
            <li>
              <button class="tile" onclick={() => app.showReviewView('points')}>
                <span class="tile-name">{t("Key points")}</span>
                {#if glimpse}
                  <span class="glimpse" use:markdown={{ language: locale.language, text: glimpse }}></span>
                  <span class="tile-foot">{pointChapters}</span>
                {:else}<span class="glimpse">{t("Once you finish a lesson")}</span>{/if}
              </button>
            </li>
            <li>
              <button class="tile" onclick={() => app.showReviewView('mistakes')}>
                <span class="tile-name">{t("Mistakes")}</span>
                {#if latestMiss}
                  <span class="glimpse" use:markdown={{ language: locale.language, text: latestMiss.question }}></span>
                  <span class="tile-foot">{t("Missed {when}", { when: ago(latestMiss.last_missed_at, now) })} · {titles(latestMiss.concept_ids)}</span>
                {:else}<span class="glimpse">{t("Nothing missed yet")}</span>{/if}
              </button>
            </li>
            {#each sheets as sheet (sheet.id)}
              <li>
                <button class="tile" onclick={() => app.showReviewView('sheets', sheet.id)}>
                  <span class="tile-name">{sheet.title}</span>
                  <!-- The top of the sheet, small, as a page seen from a step back. -->
                  <span class="glimpse page-glimpse" use:markdown={{ language: locale.language, text: sheet.markdown }}></span>
                </button>
              </li>
            {/each}
          </ul>
        </section>

        {#if sessions.length || shown.length}
          <section class="ways-in" aria-labelledby="home-sessions">
            <div class="ways-head">
              <h3 id="home-sessions">{t("Sessions")}</h3>
              {#if sessions.length > 3}
                <button class="link" onclick={() => (allSessions = !allSessions)}>{allSessions ? t("Fewer") : t("All {count}", { count: sessions.length })}</button>
              {/if}
            </div>
            <ul class="rows">
              {#each allSessions ? sessions : sessions.slice(0, 3) as session (session.id)}
                <li>
                  <button class="row" onclick={() => openSession(session.id)}>
                    <span class="name">{label(session)}</span>
                    <span class="when">{ago(session.updated_at ?? session.created_at, now)}{#if session.task_ids.length}&nbsp;· {questions(session)}{/if}</span>
                  </button>
                </li>
              {/each}
              {#if shown.length && (allSessions || sessions.length <= 3)}
                <li><button class="row" onclick={() => app.showReviewView('sets')}><span class="name">{t("Review sets from before")}</span></button></li>
              {/if}
            </ul>
          </section>
        {/if}
      </section>
    {:else}
      <div class="place">
        <nav class="review-aside" aria-label={t("Ways to review")}>
          <button class="home-link" onclick={() => app.showReviewView('home')}>
            <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M12 5l-5 5 5 5" /></svg>
            {t("Review home")}
          </button>

          <section aria-labelledby="review-read">
            <h2 id="review-read">{t("Read")}</h2>
            <ul>
              {@render item(view === 'points', () => app.showReviewView('points'), t("Key points"))}
              {@render item(view === 'mistakes', () => app.showReviewView('mistakes'), t("Mistakes"))}
              {#each sheets as sheet (sheet.id)}
                {@render item(view === 'sheets' && shownSheet?.id === sheet.id, () => app.showReviewView('sheets', sheet.id), sheet.title)}
              {/each}
            </ul>
          </section>

          {#if sessions.length || shown.length}
            <section aria-labelledby="sessions-title">
              <h2 id="sessions-title">{t("Sessions")}</h2>
              <ul class="sessions">
                {#each sessions as session (session.id)}
                  {@render item(session.id === open?.id, () => openSession(session.id), label(session), ago(session.updated_at ?? session.created_at, now))}
                {/each}
                {#if shown.length}
                  {@render item(view === 'sets', () => app.showReviewView('sets'), t("Review sets from before"))}
                {/if}
              </ul>
            </section>
          {/if}
        </nav>

        <div class="main">
          {#if view === 'session' && open}
            {#key open.id}
              <header class="view-head">
                <div>
                  <h2 class="view-title" id="drill-title">{label(open)}</h2>
                  <!-- A session Studio wrote is named by Studio; the others already say what they cover. -->
                  <p class="meta">
                    {open.title ? `${sessionScope(open)} · ` : ''}{when(open.created_at)}{#if open.task_ids.length}&nbsp;· {questions(open)}{/if}
                  </p>
                </div>
              </header>
              <DrillSession session={open} />
            {/key}
          {:else if view === 'sheets' && shownSheet}
            <!-- Keyed, so a removal asked on one sheet is not left asking on the next. -->
            {#key shownSheet.id}<SheetView sheet={shownSheet} />{/key}
          {:else if view === 'sets'}
            <header class="view-head"><h2 class="view-title">{t("Review sets from before")}</h2></header>
            <div class="stack">
              {#each shown as value (value.id)}
                <ReviewSet {value} collapsed />
              {/each}
            </div>
          {:else if view === 'mistakes'}
            <header class="view-head">
              <h2 class="view-title">{t("Mistakes")}</h2>
              <ReviewScope value={scope} onchange={setScope} />
            </header>
            <MistakesBook entries={mistakes} onretry={retry} />
          {:else}
            <header class="view-head">
              <h2 class="view-title">{t("Key points")}</h2>
              <ReviewScope value={scope} onchange={setScope} />
            </header>
            <div class="stack">
              {#each chapters as { chapter, ids } (chapter.id)}
                {@const sheet = app.chapterSheet(chapter.id)}
                <section class="chapter" aria-label={chapter.title}>
                  {#if app.chapters.length > 1}<h3 class="chapter-title">{chapter.title}</h3>{/if}
                  {#if sheet && ids.length > 1}<div class="prose connection" use:markdown={{ language: locale.language, text: sheet.connection }}></div>{/if}
                  <div class="points">
                    {#each ids as id (id)}
                      <KeyPoints value={app.keyPoints(id)!} section ontest={(point) => test(point, id)} />
                    {/each}
                  </div>
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
          {/if}
        </div>
      </div>
    {/if}
  </article>
{/if}

<style>
  .page {
    container-type: inline-size;
  }

  /* As the Studio place: a column for what there is, and the page no wider than reading needs, centred together. */
  .place {
    display: grid;
    grid-template-columns: 16rem minmax(0, 46rem);
    justify-content: center;
    column-gap: 2.5rem;
    align-items: start;
  }

  /* It stays in view while the page scrolls, and scrolls on its own when the list is long. */
  .review-aside {
    position: sticky;
    top: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 1.5rem;
    max-height: calc(100dvh - var(--topbar) - 5rem);
    overflow-y: auto;
    overscroll-behavior: contain;
    padding-right: 0.25rem;
    scrollbar-width: thin;
  }

  .review-aside section {
    display: grid;
    gap: 0.35rem;
  }

  /* A label for the list, as Studio labels its chats. */
  .review-aside h2 {
    padding-inline: 0.55rem;
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--pencil);
  }

  .review-aside ul {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 0.1rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .item,
  .home-link {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    width: 100%;
    padding: 0.35rem 0.55rem;
    border: 0;
    border-radius: var(--radius);
    background: none;
    color: var(--ink-soft);
    font: inherit;
    font-size: var(--step--1);
    text-align: left;
    cursor: pointer;
  }

  .item:hover:not([aria-current]),
  .home-link:hover {
    background: var(--raised);
    color: var(--ink);
  }

  .item[aria-current='page'] {
    background: var(--accent-wash);
    color: var(--ink);
    font-weight: 600;
  }

  /* Back to the home, at the top of the column. */
  .home-link {
    align-items: center;
    gap: 0.35rem;
    color: var(--ink);
    font-weight: 600;
  }

  .home-link svg {
    flex: none;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .when {
    flex: none;
    font-size: var(--step--2);
    font-weight: 400;
    color: var(--pencil);
  }

  .main {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 1.5rem;
    align-content: start;
    min-width: 0;
  }

  /* Each view names itself as a chapter page does, with what it covers on the right. */
  .view-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 1.25rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--rule);
  }

  .view-head > :global(.scope) {
    max-width: 60%;
  }

  .view-title {
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

  .stack,
  .chapter {
    display: grid;
    gap: 1.25rem;
  }

  .stack {
    gap: 2.25rem;
  }

  .chapter-title {
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink);
  }

  .connection {
    font-family: var(--serif);
    font-size: var(--step-0);
    line-height: 1.6;
    color: var(--ink-soft);
  }

  /* A chapter's sections on one card, as the chapter page shows them. */
  .points {
    display: grid;
    gap: 1.5rem;
    padding: 1.2rem 1.4rem 1.3rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
  }

  /* Review's home: no wider than the Studio frame, centred, a little way down the page. */
  .home {
    position: relative;
    isolation: isolate;
    display: grid;
    gap: 1rem;
    max-width: 46rem;
    margin-inline: auto;
    padding: clamp(1rem, 7vh, 4rem) 0 2rem;
  }

  /* The course's lines across the top of the page, as New course has its own, fading out on every side. */
  .lines {
    position: absolute;
    inset: -5rem -18rem auto;
    z-index: -1;
    height: 30rem;
    pointer-events: none;
    -webkit-mask-image: radial-gradient(55% 60% at 50% 40%, black 30%, transparent 75%);
    mask-image: radial-gradient(55% 60% at 50% 40%, black 30%, transparent 75%);
  }

  .lines svg {
    width: 100%;
    height: 100%;
  }

  .lines path {
    fill: none;
    stroke: color-mix(in srgb, var(--accent) 20%, transparent);
    stroke-width: 1;
    stroke-linecap: round;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
  }

  .lines path.faint {
    stroke: color-mix(in srgb, var(--accent) 11%, transparent);
  }

  .lines path.marked {
    stroke: color-mix(in srgb, var(--marker) 80%, transparent);
    stroke-width: 1.4;
  }

  .lines path.dot {
    fill: color-mix(in srgb, var(--accent) 26%, transparent);
    stroke: none;
  }

  .lines path.dot.marked {
    fill: var(--marker);
  }

  .home-head {
    display: grid;
    justify-items: center;
    gap: 0.75rem;
    padding-bottom: 0.5rem;
  }

  .home-head :global(.picker) {
    right: auto;
    left: 50%;
    translate: -50% 0;
  }

  .question {
    font-family: var(--serif);
    font-size: var(--step-3);
    font-weight: 600;
    line-height: 1.2;
    text-align: center;
    text-wrap: balance;
  }

  /* The marker's stroke, as a passage is highlighted. */
  .swipe {
    padding: 0 0.1em;
    background: linear-gradient(transparent 58%, var(--marker-wash) 58%, var(--marker-wash) 92%, transparent 92%);
    color: inherit;
  }

  /* How to drill, chosen inside the box. It shares the box's one row with Drill me, so the key hint steps aside. */
  .how {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .how button {
    padding: 0.2rem 0.6rem;
    border: 1px solid transparent;
    border-radius: 999px;
    background: none;
    color: var(--pencil);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
  }

  .how button:hover {
    color: var(--ink);
  }

  .how button[aria-checked='true'] {
    border-color: var(--rule-strong);
    background: var(--raised);
    color: var(--ink);
    font-weight: 600;
  }

  .home :global(.composer .keys) {
    display: none;
  }

  .home :global(.composer .send) {
    margin-left: auto;
  }

  /* What Studio would make leaves Review, so it is a line of links rather than more buttons. */
  .studio-ways {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: baseline;
    gap: 0.25rem 0.6rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .studio-ways ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.9rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .ways-in {
    display: grid;
    gap: 0.55rem;
  }

  .ways-in:first-of-type {
    margin-top: 2rem;
  }

  .ways-in + .ways-in {
    margin-top: 0.75rem;
  }

  .ways-in h3 {
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--pencil);
  }

  .ways-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }

  .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
  }

  .link:hover {
    text-decoration: underline;
  }

  /* As many to a row as fit, up to three, sharing the width: two are halves, not two thirds and a gap. */
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: 0.6rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .tile {
    display: grid;
    grid-template-rows: auto 1fr auto;
    align-content: start;
    gap: 0.4rem;
    width: 100%;
    height: 7.5rem;
    padding: 0.8rem 1rem 0.75rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
    color: var(--ink);
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: border-color 0.15s ease;
  }

  .tile:hover {
    border-color: var(--pencil);
  }

  .tile-name {
    overflow: hidden;
    font-size: var(--step-0);
    font-weight: 600;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  /* A glimpse, quieter than the name: two whole lines at most, as the lesson sets them. */
  .glimpse {
    display: -webkit-box;
    align-self: start;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    font-family: var(--serif);
    font-size: var(--step--1);
    line-height: 1.5;
    color: var(--pencil);
  }

  .glimpse :global(p) {
    display: inline;
    margin: 0;
  }

  .glimpse :global(p + p)::before {
    content: ' ';
  }

  /* It fills what the card leaves under the name and is cut off there, fading out. */
  .page-glimpse {
    display: block;
    align-self: stretch;
    min-height: 0;
    font-size: 0.68rem;
    line-height: 1.45;
    color: var(--ink-soft);
    -webkit-mask-image: linear-gradient(to bottom, black 55%, transparent);
    mask-image: linear-gradient(to bottom, black 55%, transparent);
  }

  .page-glimpse :global(p) {
    display: block;
  }

  .page-glimpse :global(p + p)::before {
    content: none;
  }

  .page-glimpse :global(h2) {
    margin: 0 0 0.2rem;
    font-size: 0.85rem;
  }

  .page-glimpse :global(.katex-display) {
    margin: 0.2rem 0;
  }

  .tile-foot {
    overflow: hidden;
    font-size: var(--step--2);
    white-space: nowrap;
    text-overflow: ellipsis;
    color: var(--pencil);
  }

  .rows {
    display: grid;
    margin: 0;
    padding: 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
    list-style: none;
  }

  .rows li + li {
    border-top: 1px solid var(--rule);
  }

  .row {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    width: 100%;
    padding: 0.65rem 1rem;
    border: 0;
    background: none;
    color: var(--ink);
    font: inherit;
    font-size: var(--step--1);
    font-weight: 500;
    text-align: left;
    cursor: pointer;
  }

  .row:hover {
    background: var(--accent-wash);
  }

  .rows li:first-child .row {
    border-radius: var(--radius) var(--radius) 0 0;
  }

  .rows li:last-child .row {
    border-radius: 0 0 var(--radius) var(--radius);
  }

  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .empty {
    display: grid;
    justify-items: start;
    gap: 0.5rem;
    max-width: var(--measure);
    margin-inline: auto;
    padding: 1.25rem 1.35rem;
    border: 1px dashed var(--rule-strong);
    border-radius: var(--radius);
    font-size: var(--step-0);
  }

  .empty h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  /* No room for the column beside the page (a side panel open on a narrow window): it goes above the page, its lists
     side by side. */
  @container (max-width: 52rem) {
    .place {
      grid-template-columns: minmax(0, 46rem);
      row-gap: 1.5rem;
    }

    .review-aside {
      position: static;
      grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
      align-items: start;
      max-height: none;
      padding-bottom: 1.25rem;
      border-bottom: 1px solid var(--rule);
    }

    .home-link {
      grid-column: 1 / -1;
      justify-self: start;
      width: auto;
    }

    .review-aside ul.sessions {
      max-height: 9rem;
      overflow-y: auto;
    }
  }
</style>
