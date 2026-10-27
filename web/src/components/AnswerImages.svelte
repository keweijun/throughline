<script lang="ts">
  import { t } from '../lib/i18n.svelte';

  // Images of the learner's work attached to an answer; removable while the answer is a draft.
  let { images, onremove }: { images: string[]; onremove?: (name: string) => void } = $props();
  const url = (name: string) => `/api/practice/images/${encodeURIComponent(name)}`;
</script>

{#if images.length}
  <ul class="answer-images" aria-label={t('Attached images')}>
    {#each images as name, i (name)}
      <li>
        <a href={url(name)} target="_blank" rel="noopener">
          <img src={url(name)} alt={t('Answer image {number}', { number: i + 1 })} />
        </a>
        {#if onremove}
          <button class="btn btn-quiet btn-small" onclick={() => onremove(name)} aria-label={t('Remove image {number}', { number: i + 1 })}>
            {t('Remove')}
          </button>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .answer-images {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: grid;
    justify-items: start;
    gap: 0.2rem;
  }

  img {
    display: block;
    max-width: 14rem;
    max-height: 10rem;
    object-fit: contain;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
  }
</style>
