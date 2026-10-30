<script lang="ts">
  import { t } from '../lib/i18n.svelte';

  // Images attached to an answer, a question or a note, as they were sent; `small` for the side panel's lists.
  let { images, small = false }: { images: string[]; small?: boolean } = $props();
  const url = (name: string) => `/api/images/${encodeURIComponent(name)}`;
</script>

{#if images.length}
  <ul class="attached-images" class:small aria-label={t('Attached images')}>
    {#each images as name, i (name)}
      <li>
        <a href={url(name)} target="_blank" rel="noopener">
          <img src={url(name)} alt={t('Attached image {number}', { number: i + 1 })} />
        </a>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .attached-images {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin: 0;
    padding: 0;
    list-style: none;
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

  .small {
    gap: 0.4rem;
  }

  .small img {
    width: 4rem;
    height: 4rem;
    object-fit: cover;
  }
</style>
