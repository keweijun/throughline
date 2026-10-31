<script lang="ts">
  import type { Snippet } from 'svelte';
  import { sendKeys } from '../lib/keys';
  import { editor } from '../lib/editor';
  import { markdown, hasMath } from '../lib/markdown';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { locale, t } from '../lib/i18n.svelte';

  /**
   * The one writing box. Everything that becomes part of what is sent sits inside its frame: where it goes (`header`),
   * a quoted passage, the text, a preview of its math, attached images, and the tools and send button along the bottom.
   * Actions on what the box belongs to (hints, going back to a passage) stay outside it.
   */
  let {
    id,
    value,
    onvalue,
    label,
    placeholder,
    submitLabel,
    onsubmit,
    disabled = false,
    allowEmpty = false,
    header,
    onclose,
    closeLabel,
    oncancel,
    quote,
    onremovequote,
    imagesKey,
    imagesAlone = false,
    preview = true,
    tools,
    rows = 2,
  }: {
    id?: string;
    value: string;
    onvalue: (value: string) => void;
    label: string;
    placeholder: string;
    /** A verb saying what sending does: Ask, Check answer, Add note. */
    submitLabel: string;
    onsubmit: () => void;
    disabled?: boolean;
    /** Sending with nothing written is a choice too, such as starting a lesson with no special request. */
    allowEmpty?: boolean;
    /** Where the text goes and what happens to it. */
    header?: Snippet;
    /** Shows a close button in the header: leave a follow-up, stop asking, stop editing. */
    onclose?: () => void;
    closeLabel?: string;
    /** Escape in the text calls this, as when editing something already saved. */
    oncancel?: () => void;
    quote?: { text: string; source?: string; id?: string } | null;
    onremovequote?: () => void;
    /** The draft key the attached images are kept under (app.drafts.images); without one the box takes no images. */
    imagesKey?: string;
    /** Images alone are enough to send, as for an answer worked on paper. */
    imagesAlone?: boolean;
    /** Show the rendered math under the text while it has any. */
    preview?: boolean;
    /** Switches for how the text is sent, such as pausing the lesson, at the start of the bottom row. */
    tools?: Snippet;
    rows?: number;
  } = $props();

  const IMAGE_TYPES = 'image/png,image/jpeg,image/gif,image/webp';
  const images = $derived(imagesKey ? app.drafts.images(imagesKey) : []);
  let uploading = $state(0);
  let dragging = $state(false);
  let picker = $state<HTMLInputElement>();
  const hintId = $derived(`${id ?? 'composer'}-keys`);

  const ready = $derived(!disabled && !uploading && (allowEmpty || value.trim() !== '' || (imagesAlone && images.length > 0)));

  // The preview follows the text after a pause, so typing stays smooth; the learner can hide it.
  let rendered = $state('');
  let showPreview = $state(true);
  const math = $derived(preview && hasMath(value));
  $effect(() => {
    const text = value;
    const timer = setTimeout(() => (rendered = preview && hasMath(text) ? text : ''), 150);
    return () => clearTimeout(timer);
  });

  function send() {
    if (ready) onsubmit();
  }

  async function attach(files: File[]) {
    // The key is fixed when the upload starts, so an image never lands in a box the learner has since switched to.
    const key = imagesKey;
    if (!key) return;
    for (const file of files.filter((f) => f.type.startsWith('image/'))) {
      uploading += 1;
      const result = await app.act(() => api.upload<{ image: string }>('/api/images', file));
      uploading -= 1;
      const current = app.drafts.images(key);
      if (result && !current.includes(result.image)) app.drafts.setImages(key, [...current, result.image]);
    }
  }

  function remove(name: string) {
    if (imagesKey) app.drafts.setImages(imagesKey, images.filter((n) => n !== name));
  }

  const imageFiles = (data: DataTransfer | null) => [...(data?.files ?? [])].filter((f) => f.type.startsWith('image/'));

  function paste(event: ClipboardEvent) {
    const files = imagesKey ? imageFiles(event.clipboardData) : [];
    if (!files.length) return false;
    event.preventDefault();
    void attach(files);
    return true;
  }

  function dragover(event: DragEvent) {
    if (!imagesKey || !event.dataTransfer?.types.includes('Files')) return;
    event.preventDefault();
    dragging = true;
  }

  function drop(event: DragEvent) {
    dragging = false;
    const files = imagesKey ? imageFiles(event.dataTransfer) : [];
    if (!files.length) return;
    event.preventDefault();
    void attach(files);
  }

  const url = (name: string) => `/api/images/${encodeURIComponent(name)}`;
</script>

<form
  class="composer"
  class:dragging
  aria-label={label}
  onsubmit={(event) => {
    event.preventDefault();
    send();
  }}
  ondragover={dragover}
  ondragleave={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) dragging = false;
  }}
  ondrop={drop}
>
  {#if header || onclose}
    <div class="head">
      <div class="target">{@render header?.()}</div>
      {#if onclose}
        <button type="button" class="icon" onclick={onclose} aria-label={closeLabel} title={closeLabel}>
          <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
        </button>
      {/if}
    </div>
  {/if}
  {#if quote}
    <div class="quote">
      <blockquote id={quote.id} class="prose asked-passage" use:markdown={{ language: locale.language, text: quote.text }}></blockquote>
      <p class="from">
        {#if quote.source}<span>{t("From {source}", { source: quote.source })}</span>{/if}
        <button type="button" class="link" onclick={onremovequote}>{t("Remove quote")}</button>
      </p>
    </div>
  {/if}
  <div
    class="field"
    use:editor={{ value, id, label, placeholder, rows, describedBy: hintId, onchange: onvalue, onsend: send, oncancel, onpaste: paste }}
  ></div>
  {#if math && showPreview && rendered}
    <section class="preview" aria-label={t("Preview")}>
      <div class="prose" use:markdown={{ language: locale.language, text: rendered, breaks: true }}></div>
    </section>
  {/if}
  {#if images.length || uploading}
    <ul class="images" aria-label={t("Attached images")}>
      {#each images as name, i (name)}
        <li>
          <a href={url(name)} target="_blank" rel="noopener"><img src={url(name)} alt={t('Attached image {number}', { number: i + 1 })} /></a>
          <button type="button" class="drop" onclick={() => remove(name)} aria-label={t('Remove image {number}', { number: i + 1 })} title={t('Remove image {number}', { number: i + 1 })}>
            <svg viewBox="0 0 20 20" width="10" height="10" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" /></svg>
          </button>
        </li>
      {/each}
      {#if uploading}<li class="pending" aria-live="polite">{t("Attaching…")}</li>{/if}
    </ul>
  {/if}
  <div class="bar">
    {#if imagesKey}
      <input
        bind:this={picker}
        class="visually-hidden"
        type="file"
        accept={IMAGE_TYPES}
        multiple
        tabindex="-1"
        aria-hidden="true"
        onchange={(e) => {
          const input = e.currentTarget;
          void attach([...(input.files ?? [])]);
          input.value = '';
        }}
      />
      <button type="button" class="icon" onclick={() => picker?.click()} aria-label={t("Attach images")} title={t("Attach images · or paste or drop them here")}>
        <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round">
          <rect x="2.75" y="3.75" width="14.5" height="12.5" rx="2" />
          <circle cx="7.25" cy="8" r="1.5" />
          <path d="M3 14.5l4.25-4 3.25 3 2.5-2.25 4.25 3.75" />
        </svg>
      </button>
    {/if}
    {#if math}
      <button
        type="button"
        class="icon math"
        aria-pressed={showPreview}
        onclick={() => (showPreview = !showPreview)}
        aria-label={showPreview ? t("Hide math preview") : t("Show math preview")}
        title={showPreview ? t("Hide math preview") : t("Show math preview")}
      >∑</button>
    {/if}
    {@render tools?.()}
    <span class="keys" id={hintId}>{t("{keys} to send", { keys: sendKeys })}</span>
    <button class="btn btn-small btn-primary send" type="submit" disabled={!ready}>{submitLabel}</button>
  </div>
</form>

<style>
  .composer {
    display: grid;
    min-width: 0;
    border: 1px solid var(--rule-strong);
    border-radius: calc(var(--radius) * 2);
    background: var(--raised);
    transition: border-color var(--quick) ease, box-shadow var(--quick) ease;
  }

  .composer:hover {
    border-color: var(--pencil);
  }

  .composer:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-wash);
  }

  .composer.dragging {
    border-style: dashed;
    border-color: var(--accent);
    background: var(--accent-wash);
  }

  /* The frame's own labels are interface, not text to quote: a selection dragged past a short exercise stays in it. */
  .head,
  .bar {
    user-select: none;
  }

  .head {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-width: 0;
    padding: 0.45rem 0.45rem 0 0.8rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .target {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .quote {
    display: grid;
    gap: 0.15rem;
    margin: 0.5rem 0.75rem 0;
  }

  .from {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    cursor: pointer;
  }

  .link:hover {
    text-decoration: underline;
  }

  .preview {
    margin: 0 0.8rem;
    padding: 0.45rem 0 0.2rem;
    border-top: 1px dashed var(--rule);
    font-size: var(--step-0);
    color: var(--ink-soft);
    max-height: 14rem;
    overflow: auto;
  }

  /* The preview checks the math, so it keeps the size of the text it renders. */
  .preview .prose {
    font-size: inherit;
  }

  .images {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0;
    padding: 0.4rem 0.8rem 0.1rem;
    list-style: none;
  }

  .images li {
    position: relative;
  }

  .images img {
    display: block;
    width: 4.5rem;
    height: 4.5rem;
    object-fit: cover;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
  }

  .images .drop {
    position: absolute;
    top: -0.4rem;
    right: -0.4rem;
    display: grid;
    place-items: center;
    width: 1.25rem;
    height: 1.25rem;
    padding: 0;
    border: 1px solid var(--rule-strong);
    border-radius: 50%;
    background: var(--raised);
    color: var(--ink-soft);
    cursor: pointer;
  }

  .images .drop:hover {
    color: var(--danger);
    border-color: var(--danger);
  }

  .images .pending {
    display: grid;
    place-items: center;
    width: 4.5rem;
    height: 4.5rem;
    border: 1px dashed var(--rule-strong);
    border-radius: var(--radius);
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.35rem;
    padding: 0.3rem 0.4rem 0.4rem 0.45rem;
  }

  .icon {
    display: grid;
    place-items: center;
    flex: none;
    width: 1.9rem;
    height: 1.9rem;
    padding: 0;
    border: 0;
    border-radius: var(--radius);
    background: none;
    color: var(--pencil);
    font-size: 1rem;
    cursor: pointer;
  }

  .icon:hover {
    background: var(--accent-wash);
    color: var(--accent);
  }

  .math {
    font-family: var(--serif);
  }

  .math[aria-pressed='true'] {
    color: var(--accent);
  }

  .keys {
    margin-left: auto;
    padding-inline: 0.25rem;
    font-size: var(--step--1);
    color: var(--pencil);
    opacity: 0;
    transition: opacity var(--quick) ease;
  }

  /* The keys matter while writing; at rest the bar shows only what can be done. */
  .composer:focus-within .keys {
    opacity: 1;
  }

  .send {
    flex: none;
  }

  .keys + .send {
    margin-left: 0;
  }
</style>
