<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { onDestroy, onMount, tick, untrack } from 'svelte';
  import type { PDFDocumentProxy, PDFPageProxy, PageViewport, RenderTask } from 'pdfjs-dist/legacy/build/pdf.mjs';
  import { openPdf, pdfjs } from '../lib/pdf';
  import { mark, clear, type Passage } from '../lib/highlight';

  let {
    url,
    document: documentKey = url,
    page: target,
    label,
    highlights = [],
    current = $bindable(target),
  }: {
    url: string;
    /** Identifies the file whatever page the URL was asked for, so the loaded document is reused. */
    document?: string;
    page: number;
    label: string;
    highlights?: { page: number; passage: Passage }[];
    current?: number;
  } = $props();

  let scroller: HTMLDivElement | undefined = $state();
  let doc = $state<PDFDocumentProxy | null>(null);
  let failed = $state(false);
  let fit = $state(true);
  let zoom = $state(1);
  let base = $state({ width: 612, height: 792 });
  let pageInput = $state('1');
  let width = $state(0);

  const scale = $derived(fit && width ? Math.max(0.4, (width - 32) / base.width) : zoom);
  const pages = $derived(doc ? Array.from({ length: doc.numPages }, (_, i) => i + 1) : []);

  type Rendering = { scale: number; task?: RenderTask; page?: PDFPageProxy };
  const rendered = new Map<number, Rendering>();
  const elements = new Map<number, HTMLElement>();
  // Highlight keys are global, so each reader uses its own and remembers which it painted.
  const prefix = `pdf-${Math.random().toString(36).slice(2)}-`;
  const marked = new Set<number>();
  let observer: IntersectionObserver | null = null;
  let release: IntersectionObserver | null = null;
  let resize: ResizeObserver | null = null;
  let ready = $state(false);

  // Pages are drawn as they come near the viewport and freed again once far away, so a long PDF does not keep a
  // canvas for every page it has shown. Approaching a freed page draws it again.
  const NEAR = 600;
  const FAR = 2400;

  onMount(async () => {
    try {
      doc = await openPdf(url, documentKey);
      const first = await doc.getPage(1);
      const viewport = first.getViewport({ scale: 1 });
      base = { width: viewport.width, height: viewport.height };
    } catch {
      failed = true;
      return;
    }
    await tick();
    if (!scroller) return; // unmounted while loading
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) if (entry.isIntersecting) void draw(Number((entry.target as HTMLElement).dataset.page));
      },
      { root: scroller, rootMargin: `${NEAR}px 0px` },
    );
    release = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) if (!entry.isIntersecting) free(Number((entry.target as HTMLElement).dataset.page));
      },
      { root: scroller, rootMargin: `${FAR}px 0px` },
    );
    for (const element of elements.values()) {
      observer.observe(element);
      release.observe(element);
    }
    width = scroller.clientWidth;
    resize = new ResizeObserver(() => (width = scroller!.clientWidth));
    resize.observe(scroller);
    await tick();
    ready = true;
  });

  // Open at the cited page, and follow later citations into the same document without rebuilding the reader.
  let landed = false;
  $effect(() => {
    const page = target;
    if (!ready) return;
    untrack(() => go(page, landed ? 'smooth' : 'instant'));
    landed = true;
  });

  function markPage(number: number) {
    const text = elements.get(number)?.querySelector<HTMLElement>('.textLayer');
    if (!text) return;
    const passages = highlights.filter((h) => h.page === number).map((h) => h.passage);
    mark('mine', prefix + number, text, passages, { loose: true });
    marked.add(number);
  }

  function unmark(number: number) {
    if (marked.delete(number)) clear('mine', prefix + number);
  }

  $effect(() => {
    void highlights;
    for (const number of rendered.keys()) markPage(number);
  });

  onDestroy(() => {
    // Page elements may already be gone here, so clear what was painted rather than what is on screen.
    for (const number of [...marked]) unmark(number);
    observer?.disconnect();
    release?.disconnect();
    resize?.disconnect();
    for (const r of rendered.values()) {
      r.task?.cancel();
      r.page?.cleanup();
    }
    rendered.clear();
  });

  /** Drops a page's canvas and text layer; its element keeps its size so scrolling does not jump. */
  function free(number: number) {
    const r = rendered.get(number);
    if (!r) return;
    rendered.delete(number);
    r.task?.cancel();
    unmark(number);
    const layers = elements.get(number)?.querySelector('.layers');
    const canvas = layers?.querySelector('canvas');
    // Shrinking the canvas releases its backing memory straight away instead of at garbage collection.
    if (canvas) canvas.width = canvas.height = 0;
    layers?.replaceChildren();
    r.page?.cleanup();
  }

  // Redraw visible pages when the scale changes (zoom, or the panel being resized in fit mode).
  $effect(() => {
    const s = scale;
    for (const [number, r] of rendered) {
      if (r.scale === s) continue;
      const element = elements.get(number);
      if (element && visible(element)) {
        r.task?.cancel();
        rendered.delete(number);
        void draw(number); // the old canvas stays, stretched, until the new one replaces it
      } else free(number);
    }

  });

  function visible(element: HTMLElement) {
    const box = element.getBoundingClientRect();
    const view = scroller!.getBoundingClientRect();
    return box.bottom > view.top - NEAR && box.top < view.bottom + NEAR;
  }

  function register(node: HTMLElement, number: number) {
    elements.set(number, node);
    observer?.observe(node);
    release?.observe(node);
    return { destroy: () => elements.delete(number) };
  }

  async function draw(number: number) {
    if (!doc || rendered.has(number)) return;
    const s = scale;
    const entry: Rendering = { scale: s };
    rendered.set(number, entry);
    const element = elements.get(number);
    if (!element) return;
    const pdf = await pdfjs();
    const page = await doc.getPage(number);
    if (rendered.get(number) !== entry) return; // freed or rescaled meanwhile
    entry.page = page;
    const viewport: PageViewport = page.getViewport({ scale: s });
    const ratio = window.devicePixelRatio || 1;
    const canvas = document.createElement('canvas');
    canvas.width = Math.floor(viewport.width * ratio);
    canvas.height = Math.floor(viewport.height * ratio);
    const text = document.createElement('div');
    text.className = 'textLayer';
    entry.task = page.render({
      canvas,
      canvasContext: canvas.getContext('2d')!,
      viewport,
      transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
    });
    try {
      await entry.task.promise;
    } catch {
      canvas.width = canvas.height = 0;
      return; // cancelled by a newer scale, or freed
    }
    if (rendered.get(number) !== entry) {
      canvas.width = canvas.height = 0;
      return;
    }
    element.style.width = `${viewport.width}px`;
    element.style.height = `${viewport.height}px`;
    element.style.setProperty('--total-scale-factor', String(s));
    const old = element.querySelector('.layers canvas');
    if (old instanceof HTMLCanvasElement) old.width = old.height = 0;
    element.querySelector('.layers')!.replaceChildren(canvas, text);
    await new pdf.TextLayer({ textContentSource: page.streamTextContent(), container: text, viewport }).render();
    if (rendered.get(number) === entry) markPage(number);
  }

  // A jump to a page owns the position until its scroll ends: intermediate positions are not the current page, and pages
  // that change size while drawing can stop a smooth scroll short, so the landing is checked and corrected.
  let jumping: number | null = null;
  let settle: ReturnType<typeof setTimeout> | undefined;

  function land() {
    clearTimeout(settle);
    const n = jumping;
    jumping = null;
    const element = n === null ? undefined : elements.get(n);
    if (element && scroller && Math.abs(scroller.scrollTop - (element.offsetTop - 12)) > 2) {
      scroller.scrollTo({ top: element.offsetTop - 12, behavior: 'instant' });
    }
    if (n !== null) {
      current = n;
      pageInput = String(n);
    }
  }

  function onScroll() {
    if (!scroller) return;
    if (jumping !== null) {
      // Some browsers have no scrollend event; settle once scrolling pauses.
      clearTimeout(settle);
      settle = setTimeout(land, 150);
      return;
    }
    const middle = scroller.getBoundingClientRect().top + scroller.clientHeight / 3;
    for (const [number, element] of elements) {
      const box = element.getBoundingClientRect();
      if (box.top <= middle && box.bottom >= middle) {
        current = number;
        pageInput = String(number);
        return;
      }
    }
  }

  function go(number: number, behavior: ScrollBehavior = 'smooth') {
    if (!doc) return;
    if (!Number.isInteger(number)) {
      pageInput = String(current); // not a page number: show where the reader is again
      return;
    }
    const n = Math.min(Math.max(1, number), doc.numPages);
    const element = elements.get(n);
    if (!element || !scroller) return;
    current = n;
    pageInput = String(n);
    if (Math.abs(scroller.scrollTop - (element.offsetTop - 12)) <= 2) return;
    jumping = n;
    scroller.scrollTo({ top: element.offsetTop - 12, behavior });
    clearTimeout(settle);
    settle = setTimeout(land, behavior === 'smooth' ? 1000 : 150);
  }

  function setZoom(value: number) {
    const keep = current;
    zoom = Math.min(Math.max(value, 0.5), 3);
    fit = false;
    requestAnimationFrame(() => go(keep, 'instant'));
  }

  function fitWidth() {
    const keep = current;
    fit = true;
    requestAnimationFrame(() => go(keep, 'instant'));
  }
</script>

<div class="reader">
  <div class="toolbar" role="toolbar" aria-label={t("PDF reader")}>
    <div class="group">
      <button class="btn btn-quiet btn-small" onclick={() => go(current - 1)} disabled={current <= 1} aria-label={t("Previous page")}>‹</button>
      <form class="page" onsubmit={(e) => (e.preventDefault(), go(/^\s*\d+\s*$/.test(pageInput) ? Number(pageInput) : NaN))}>
        <input aria-label={t("Page number")} inputmode="numeric" pattern="[0-9]*" bind:value={pageInput} onblur={() => (pageInput = String(current))} />
        <span>{t("of {count}", { count: doc?.numPages ?? '…' })}</span>
      </form>
      <button class="btn btn-quiet btn-small" onclick={() => go(current + 1)} disabled={!doc || current >= doc.numPages} aria-label={t("Next page")}>›</button>
    </div>
    <div class="group">
      <button class="btn btn-quiet btn-small" onclick={() => setZoom(scale - 0.15)} aria-label={t("Zoom out")}>−</button>
      <span class="zoom">{Math.round(scale * 100)}%</span>
      <button class="btn btn-quiet btn-small" onclick={() => setZoom(scale + 0.15)} aria-label={t("Zoom in")}>+</button>
      <button class="btn btn-quiet btn-small" aria-pressed={fit} onclick={fitWidth}>{t("Fit width")}</button>
    </div>
    {#if current !== target}
      <button class="btn btn-small cited-jump" onclick={() => go(target)}>{t("Back to cited page")}</button>
    {/if}
  </div>

  <!-- Focusable so the pages can be scrolled with the keyboard. -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <div class="pages" bind:this={scroller} onscroll={onScroll} onscrollend={() => jumping !== null && land()} data-source-label={label} tabindex="0" role="region" aria-label={label}>

    {#if failed}
      <p class="problem">{t("This PDF could not be displayed here. Open the original instead.")}</p>
    {/if}
    {#each pages as number (number)}
      <section
        class="pdf-page"
        class:cited={number === target}
        data-page={number}
        data-unit="page-{number}"
        aria-label={t("Page {page}", { page: number })}
        style:width="{base.width * scale}px"
        style:height="{base.height * scale}px"
        use:register={number}
      >
        <div class="layers"></div>
        {#if number === target}<span class="cited-tag">{t("Cited page")}</span>{/if}
      </section>
    {/each}
  </div>
</div>

<style>
  .reader {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    overflow: hidden;
    background: color-mix(in srgb, var(--ground) 70%, var(--rule));
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.25rem 0.75rem;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid var(--rule);
    background: var(--sheet);
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .group {
    display: flex;
    align-items: center;
    gap: 0.15rem;
  }

  .page {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-variant-numeric: tabular-nums;
  }

  .page input {
    width: 3rem;
    padding: 0.15rem 0.3rem;
    text-align: center;
    font-size: var(--step--1);
  }

  .zoom {
    min-width: 3rem;
    text-align: center;
    font-variant-numeric: tabular-nums;
  }

  .cited-jump {
    border-color: var(--marker);
  }

  .pages {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    align-items: safe center;
    gap: 1rem;
    outline: none;
  }

  .pdf-page {
    position: relative;
    flex: none;
    background: white;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.12), 0 6px 18px rgb(0 0 0 / 0.08);
    --scale-round-x: 1px;
    --scale-round-y: 1px;
  }

  .pdf-page.cited {
    outline: 3px solid var(--marker);
    outline-offset: 3px;
  }

  .cited-tag {
    position: absolute;
    top: -0.7rem;
    right: 0.6rem;
    padding: 0 0.45rem;
    border-radius: 4px;
    background: var(--marker);
    color: #2a2208;
    font-size: 0.72rem;
    font-weight: 600;
    line-height: 1.4rem;
  }

  .layers :global(canvas) {
    display: block;
    width: 100%;
    height: 100%;
  }

  :global([data-theme='dark']) .layers :global(canvas) {
    filter: brightness(0.88) contrast(1.05);
  }

  @media (prefers-color-scheme: dark) {
    :global(:root:not([data-theme='light'])) .layers :global(canvas) {
      filter: brightness(0.88) contrast(1.05);
    }
  }

  .problem {
    color: var(--danger);
    font-size: var(--step-0);
  }

  /* pdf.js text layer: transparent text positioned over the canvas so it can be selected. */
  .layers :global(.textLayer) {
    position: absolute;
    inset: 0;
    overflow: clip;
    line-height: 1;
    text-align: initial;
    transform-origin: 0 0;
    forced-color-adjust: none;
    --min-font-size: 1;
    --text-scale-factor: calc(var(--total-scale-factor) * var(--min-font-size));
    --min-font-size-inv: calc(1 / var(--min-font-size));
  }

  .layers :global(.textLayer :is(span, br)) {
    position: absolute;
    color: transparent;
    white-space: pre;
    cursor: text;
    transform-origin: 0% 0%;
  }

  .layers :global(.textLayer > :not(.markedContent)),
  .layers :global(.textLayer .markedContent span:not(.markedContent)) {
    --font-height: 0;
    --scale-x: 1;
    --rotate: 0deg;
    font-size: calc(var(--text-scale-factor) * var(--font-height));
    transform: rotate(var(--rotate)) scaleX(var(--scale-x)) scale(var(--min-font-size-inv));
  }

  .layers :global(.textLayer .markedContent) {
    display: contents;
  }

  .layers :global(.textLayer ::selection) {
    background: rgb(240 210 92 / 0.55);
  }
</style>
