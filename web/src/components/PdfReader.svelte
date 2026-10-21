<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { onDestroy, onMount, tick } from 'svelte';
  import type { PDFDocumentProxy, PageViewport, RenderTask } from 'pdfjs-dist/legacy/build/pdf.mjs';
  import { openPdf, pdfjs } from '../lib/pdf';

  let { url, page: target, label }: { url: string; page: number; label: string } = $props();

  let scroller: HTMLDivElement | undefined = $state();
  let doc = $state<PDFDocumentProxy | null>(null);
  let failed = $state(false);
  let fit = $state(true);
  let zoom = $state(1);
  let base = $state({ width: 612, height: 792 });
  let current = $state(1);
  let pageInput = $state('1');
  let width = $state(0);

  const scale = $derived(fit && width ? Math.max(0.4, (width - 32) / base.width) : zoom);
  const pages = $derived(doc ? Array.from({ length: doc.numPages }, (_, i) => i + 1) : []);

  const rendered = new Map<number, { scale: number; task?: RenderTask }>();
  const elements = new Map<number, HTMLElement>();
  let observer: IntersectionObserver | null = null;
  let resize: ResizeObserver | null = null;

  onMount(async () => {
    try {
      doc = await openPdf(url);
      const first = (await doc.getPage(1)).getViewport({ scale: 1 });
      base = { width: first.width, height: first.height };
    } catch {
      failed = true;
      return;
    }
    await tick();
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) if (entry.isIntersecting) void draw(Number((entry.target as HTMLElement).dataset.page));
      },
      { root: scroller, rootMargin: '600px 0px' },
    );
    for (const element of elements.values()) observer.observe(element);
    width = scroller!.clientWidth;
    resize = new ResizeObserver(() => (width = scroller!.clientWidth));
    resize.observe(scroller!);
    await tick();
    go(target, 'instant');
  });

  onDestroy(() => {
    observer?.disconnect();
    resize?.disconnect();
    for (const r of rendered.values()) r.task?.cancel();
  });

  // Redraw visible pages when the scale changes (zoom, or the panel being resized in fit mode).
  $effect(() => {
    const s = scale;
    for (const [number, r] of rendered) {
      if (r.scale === s) continue;
      r.task?.cancel();
      rendered.delete(number);
      const element = elements.get(number);
      if (element && visible(element)) void draw(number);
    }
  });

  function visible(element: HTMLElement) {
    const box = element.getBoundingClientRect();
    const view = scroller!.getBoundingClientRect();
    return box.bottom > view.top - 600 && box.top < view.bottom + 600;
  }

  function register(node: HTMLElement, number: number) {
    elements.set(number, node);
    observer?.observe(node);
    return { destroy: () => elements.delete(number) };
  }

  async function draw(number: number) {
    if (!doc || rendered.has(number)) return;
    const s = scale;
    const entry: { scale: number; task?: RenderTask } = { scale: s };
    rendered.set(number, entry);
    const element = elements.get(number);
    if (!element) return;
    const pdf = await pdfjs();
    const page = await doc.getPage(number);
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
      return; // cancelled by a newer scale
    }
    if (rendered.get(number) !== entry) return;
    element.style.width = `${viewport.width}px`;
    element.style.height = `${viewport.height}px`;
    element.style.setProperty('--total-scale-factor', String(s));
    element.querySelector('.layers')!.replaceChildren(canvas, text);
    await new pdf.TextLayer({ textContentSource: page.streamTextContent(), container: text, viewport }).render();
  }

  function onScroll() {
    if (!scroller) return;
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
    const n = Math.min(Math.max(1, number), doc.numPages);
    const element = elements.get(n);
    if (!element || !scroller) return;
    scroller.scrollTo({ top: element.offsetTop - 12, behavior });
    current = n;
    pageInput = String(n);
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
      <form class="page" onsubmit={(e) => (e.preventDefault(), go(Number(pageInput)))}>
        <input aria-label={t("Page number")} inputmode="numeric" bind:value={pageInput} />
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

  <div class="pages" bind:this={scroller} onscroll={onScroll} data-source-label={label} tabindex="-1">
    {#if failed}
      <p class="problem">{t("This PDF could not be displayed here. Open the original instead.")}</p>
    {/if}
    {#each pages as number (number)}
      <section
        class="pdf-page"
        class:cited={number === target}
        data-page={number}
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
