<script lang="ts">
  import type { Snippet } from 'svelte';
  import { enterToSend } from '../lib/keys';
  import { autogrow } from '../lib/autogrow';
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';

  // The writing box Questions and Notes pin to the bottom of the panel, so new items arrive just above where they were typed.
  let {
    id,
    value,
    onvalue,
    label,
    placeholder,
    submitLabel,
    disabled = false,
    onsubmit,
    context,
    onclear,
    clearLabel,
    quote,
    onremovequote,
    options,
  }: {
    id: string;
    value: string;
    onvalue: (value: string) => void;
    label: string;
    placeholder: string;
    submitLabel: string;
    disabled?: boolean;
    onsubmit: () => void;
    /** What the box writes to, such as the thread a follow-up joins or the section a note is added to. */
    context?: Snippet;
    onclear?: () => void;
    clearLabel?: string;
    quote?: { text: string; source?: string; id?: string } | null;
    onremovequote?: () => void;
    options?: Snippet;
  } = $props();
</script>

<form
  class="composer"
  onsubmit={(event) => {
    event.preventDefault();
    if (!disabled && value.trim()) onsubmit();
  }}
>
  {#if context}
    <div class="context">
      <div class="target">{@render context()}</div>
      {#if onclear}
        <button type="button" class="btn btn-quiet btn-small clear" onclick={onclear} aria-label={clearLabel} title={clearLabel}>
          <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
        </button>
      {/if}
    </div>
  {/if}
  {#if quote}
    <div class="quote">
      <blockquote id={quote.id} class="prose asked-passage" use:markdown={{ language: locale.language, text: quote.text }}></blockquote>
      {#if quote.source}<p class="from">{t("From {source}", { source: quote.source })}</p>{/if}
      <button type="button" class="btn btn-quiet btn-small btn-flush" onclick={onremovequote}>{t("Remove quote")}</button>
    </div>
  {/if}
  <textarea
    {id}
    rows="2"
    value={value}
    oninput={(event) => onvalue(event.currentTarget.value)}
    use:autogrow={value}
    use:enterToSend
    aria-label={label}
    {placeholder}
  ></textarea>
  <div class="row">
    {@render options?.()}
    <button class="btn btn-small btn-primary send" type="submit" disabled={disabled || !value.trim()}>{submitLabel}</button>
  </div>
</form>

<style>
  .composer {
    position: sticky;
    bottom: 0;
    z-index: 2;
    display: grid;
    gap: 0.45rem;
    margin-top: auto;
    padding: 0.7rem 0 1rem;
    background: var(--sheet);
    box-shadow: 0 -1px 0 var(--rule);
  }

  .context {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    min-width: 0;
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

  .clear {
    flex: none;
    min-height: 1.6rem;
    padding: 0.2rem 0.35rem;
    color: var(--pencil);
  }

  .quote {
    display: grid;
    gap: 0.2rem;
  }

  .quote .btn {
    justify-self: start;
  }

  .from {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  textarea {
    min-height: 2.75rem;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.6rem;
  }

  .send {
    margin-left: auto;
  }
</style>
