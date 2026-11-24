<script lang="ts">
  import { coverPattern, HEIGHT, WIDTH } from '../lib/covers';
  import type { LibraryCourse } from '../lib/types';

  /**
   * A course's cover on its library card (ADR 0027): the subject's short name, chosen by Codex, over the pattern of
   * thin lines it chose with it. A course Codex has not given a cover yet shows its title over a pattern, so no cover
   * is ever a blank: a short title as a name would be, a long one on two smaller lines.
   */
  let { course, large = false }: { course: LibraryCourse; large?: boolean } = $props();

  const title = $derived(course.title ?? course.name);
  // A title longer than a cover name may be (covers.NAME_LENGTH) wraps rather than shrinking to fit one line.
  const long = $derived(!course.cover?.name && title.length > 16);

  const marks = $derived(coverPattern(course.cover?.pattern, course.name));

  /** Shrinks a name too long for its cover, and tells the pattern how much paper the name takes, so it clears that much. */
  function fit(node: HTMLElement) {
    const measure = () => {
      const cover = node.parentElement!;
      node.style.scale = '';
      const room = cover.clientWidth * 0.6;
      const scale = Math.min(1, room / node.offsetWidth);
      if (scale < 1) node.style.scale = String(scale);
      cover.style.setProperty('--name', `${Math.round(((node.offsetWidth * scale) / cover.clientWidth) * 100)}%`);
    };
    const watch = new ResizeObserver(measure);
    watch.observe(node.parentElement!);
    void document.fonts?.ready.then(measure);
    return { destroy: () => watch.disconnect() };
  }
</script>

<div class="cover" class:large class:long aria-hidden="true">
  <svg viewBox="0 0 {WIDTH} {HEIGHT}" preserveAspectRatio="xMaxYMid slice">
    {#each marks as mark}<path d={mark.d} class={mark.tone} class:dot={mark.dot} class:wide={mark.wide} />{/each}
  </svg>
  {#if course.cover?.name}
    {#key course.cover.name}<span class="name" use:fit>{course.cover.name}</span>{/key}
  {:else if long}
    <span class="name wrap">{title}</span>
  {:else}
    {#key title}<span class="name" use:fit>{title}</span>{/key}
  {/if}
</div>

<style>
  .cover {
    position: relative;
    display: grid;
    place-items: center start;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background:
      radial-gradient(120% 140% at 88% 0%, color-mix(in srgb, var(--marker) 11%, transparent), transparent 55%),
      linear-gradient(160deg, var(--accent-wash), color-mix(in srgb, var(--accent-wash) 40%, var(--sheet)));
  }

  /* The pattern clears to the left, where the name stands. */
  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    mask-image: linear-gradient(90deg, transparent calc(var(--name, 0%) - 6%), #000 calc(var(--name, 0%) + 30%));
  }

  path {
    fill: none;
    stroke: color-mix(in srgb, var(--accent) 24%, transparent);
    stroke-width: 1;
    stroke-linecap: round;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
  }

  path.faint {
    stroke: color-mix(in srgb, var(--accent) 13%, transparent);
  }

  path.marked {
    stroke: var(--marker);
    stroke-width: 1.6;
  }

  path.wide {
    stroke-width: 2;
  }

  path.wide.marked {
    stroke-width: 2.4;
  }

  path.dot {
    fill: color-mix(in srgb, var(--accent) 34%, transparent);
    stroke: none;
  }

  path.dot.faint {
    fill: color-mix(in srgb, var(--accent) 16%, transparent);
  }

  path.dot.marked {
    fill: var(--marker);
  }

  .name {
    position: relative;
    transform-origin: left center;
    padding-left: 1.15rem;
    color: var(--accent);
    font: 600 1.85rem/1.15 var(--serif);
    letter-spacing: 0.03em;
    white-space: nowrap;
  }

  /* A long title is set on two lines and the pattern clears the left part of the cover for it. */
  .long {
    --name: 58%;
  }

  .name.wrap {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    max-width: 62%;
    font-size: 1.35rem;
    letter-spacing: 0.01em;
    white-space: normal;
  }

  .large .name.wrap {
    font-size: 1.9rem;
  }

  .large .name {
    padding-left: 1.75rem;
    font-size: 2.6rem;
  }
</style>
