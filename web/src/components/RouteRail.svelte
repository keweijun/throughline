<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  const route = $derived(app.state?.curriculum.route ?? []);
  const currentIndex = $derived(app.routeIndex(app.currentId));
  const prepared = $derived(
    new Set((app.state?.preparation.jobs ?? []).filter((j) => j.status === 'ready').map((j) => j.concept_id)),
  );

  function stateOf(id: string, index: number) {
    if (id === app.currentId) return 'current';
    if (index < currentIndex || app.hasLesson(id)) return 'visited';
    return 'upcoming';
  }

  const label = { current: 'Current section', visited: 'Visited', upcoming: 'Not started' };
</script>

<nav id="route" class="rail" class:open={app.routeOpen} aria-label={t("Course route")}>
  <h2>{t("Route")}</h2>
  <ol>
    {#each route as id, index (id)}
      {@const concept = app.concept(id)}
      {@const status = stateOf(id, index)}
      <li class={status}>
        <button
          class:viewing={id === app.viewingId}
          aria-current={id === app.viewingId ? 'page' : undefined}
          onclick={() => app.view(id)}
        >
          <span class="node" aria-hidden="true"></span>
          <span class="text">
            <span class="name">{concept?.title ?? id}</span>
            {#if status === 'current'}
              <span class="meta">{t("You are here")}</span>
            {:else if prepared.has(id)}
              <span class="meta">{t("Prepared")}</span>
            {/if}
            <span class="visually-hidden">{diagnostic(label[status])}</span>
          </span>
        </button>
      </li>
    {/each}
  </ol>
  <button class="btn btn-quiet btn-small settings" onclick={() => (app.settingsOpen = true)}>{t("Model settings")}</button>
</nav>

<style>
  .rail {
    position: sticky;
    top: var(--topbar);
    max-height: calc(100vh - var(--topbar));
    overflow-y: auto;
    padding: 2.5rem 0.75rem 2rem clamp(0.75rem, 2vw, 1.5rem);
  }

  h2 {
    margin: 0 0 0.75rem 0.55rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  ol {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    position: relative;
  }

  /* The thread connecting route nodes. */
  li:not(:last-child)::before {
    content: '';
    position: absolute;
    left: 1.07rem;
    top: 1.45rem;
    bottom: -0.75rem;
    width: 2px;
    background: var(--rule);
  }

  li.visited:not(:last-child)::before {
    background: var(--accent);
    opacity: 0.45;
  }

  button {
    display: flex;
    gap: 0.7rem;
    width: 100%;
    padding: 0.5rem 0.55rem;
    border: 0;
    border-radius: var(--radius);
    background: transparent;
    text-align: left;
    cursor: pointer;
    color: var(--ink-soft);
  }

  button:hover {
    background: color-mix(in srgb, var(--accent-wash) 60%, transparent);
  }

  button.viewing {
    background: var(--accent-wash);
    color: var(--ink);
  }

  .node {
    position: relative;
    z-index: 1;
    flex: none;
    width: 0.75rem;
    height: 0.75rem;
    margin-top: 0.32rem;
    border: 2px solid var(--rule-strong);
    border-radius: 50%;
    background: var(--ground);
  }

  .visited .node {
    border-color: var(--accent);
    background: var(--accent);
  }

  .current .node {
    border-color: var(--accent);
    background: var(--marker);
    box-shadow: 0 0 0 3px var(--marker-wash);
  }

  .text {
    display: grid;
    gap: 0.05rem;
    min-width: 0;
  }

  .name {
    font-size: var(--step-0);
    line-height: 1.35;
  }

  .current .name {
    font-weight: 600;
    color: var(--ink);
  }

  .meta {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .settings {
    display: none;
    margin-top: 1.5rem;
  }

  @media (max-width: 56rem) {
    .rail {
      position: fixed;
      top: var(--topbar);
      bottom: 0;
      left: 0;
      z-index: 35;
      width: min(20rem, 86vw);
      max-height: none;
      padding-top: 1.5rem;
      background: var(--sheet);
      border-right: 1px solid var(--rule);
      box-shadow: var(--shadow);
      transform: translateX(-102%);
      transition: transform 0.2s ease;
      visibility: hidden;
    }

    .rail.open {
      transform: none;
      visibility: visible;
    }

    .settings {
      display: inline-flex;
    }
  }
</style>
