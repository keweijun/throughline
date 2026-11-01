<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio, type StudioRequest } from '../lib/studio.svelte';

  /**
   * Something Codex is waiting on: an approval (a command, file changes, more access) or questions. As in Codex, Enter
   * approves and Escape declines; the approve button takes focus when the request arrives, so either key works at once.
   */
  let { request, focus = false }: { request: StudioRequest; focus?: boolean } = $props();

  let busy = $state(false);
  let approve = $state<HTMLButtonElement>();
  const chosen: Record<string, string> = $state({});
  const other: Record<string, string> = $state({});

  $effect(() => {
    if (focus && approve) approve.focus();
  });

  const title = $derived(
    request.method === 'item/commandExecution/requestApproval'
      ? t('Codex wants to run a command')
      : request.method === 'item/fileChange/requestApproval'
        ? t('Codex wants to change files')
        : request.method === 'item/permissions/requestApproval'
          ? t('Codex asks for more access')
          : t('Codex has a question'),
  );

  async function decide(decision: 'accept' | 'acceptForSession' | 'decline') {
    if (busy) return;
    busy = true;
    try {
      await studio.answer(request, { decision });
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
    }
    busy = false;
  }

  async function reply(event: SubmitEvent) {
    event.preventDefault();
    if (busy || request.method !== 'item/tool/requestUserInput') return;
    const answers: Record<string, string[]> = {};
    for (const question of request.params.questions) {
      const answer = chosen[question.id] === '__other' ? other[question.id]?.trim() : chosen[question.id];
      answers[question.id] = answer ? [answer] : [];
    }
    busy = true;
    try {
      await studio.answer(request, { answers });
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
    }
    busy = false;
  }

  function keys(event: KeyboardEvent) {
    if (event.key === 'Escape' && request.method !== 'item/tool/requestUserInput') {
      event.preventDefault();
      event.stopPropagation();
      void decide('decline');
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<section class="request" aria-label={title} onkeydown={keys} role="group">
  <h3>{title}</h3>
  {#if request.method === 'item/tool/requestUserInput'}
    <form onsubmit={reply}>
      {#each request.params.questions as question (question.id)}
        <fieldset>
          <legend>{question.header || question.question}</legend>
          {#if question.header}<p>{question.question}</p>{/if}
          {#each question.options ?? [] as option (option.label)}
            <label class="option">
              <input type="radio" name={`q-${request.id}-${question.id}`} value={option.label} bind:group={chosen[question.id]} />
              <span>{option.label}{#if option.description}<small>{option.description}</small>{/if}</span>
            </label>
          {/each}
          {#if question.isOther || !question.options?.length}
            {#if question.options?.length}
              <label class="option">
                <input type="radio" name={`q-${request.id}-${question.id}`} value="__other" bind:group={chosen[question.id]} />
                <span>{t("Other")}</span>
              </label>
            {/if}
            <input
              class="answer"
              type={question.isSecret ? 'password' : 'text'}
              aria-label={question.question}
              placeholder={t("Your answer")}
              bind:value={other[question.id]}
              oninput={() => (chosen[question.id] = '__other')}
            />
          {/if}
        </fieldset>
      {/each}
      <div class="actions"><button class="btn btn-small btn-primary" disabled={busy}>{t("Answer")}</button></div>
    </form>
  {:else}
    {#if request.params.reason}<p>{request.params.reason}</p>{/if}
    {#if request.method === 'item/commandExecution/requestApproval' && request.params.command}
      <pre><code>{request.params.command}</code></pre>
    {/if}
    {#if request.params.grantRoot}<p>{t("Write access to {folder}", { folder: request.params.grantRoot })}</p>{/if}
    <div class="actions">
      <button bind:this={approve} class="btn btn-small btn-primary" disabled={busy} onclick={() => decide('accept')} title={t("Enter")}>{t("Approve")}</button>
      <button class="btn btn-small" disabled={busy} onclick={() => decide('acceptForSession')}>{t("Approve for this chat")}</button>
      <button class="btn btn-small btn-quiet" disabled={busy} onclick={() => decide('decline')} title={t("Esc")}>{t("Decline")}</button>
    </div>
  {/if}
</section>

<style>
  .request {
    display: grid;
    gap: 0.5rem;
    padding: 0.7rem 0.8rem;
    border: 1px solid var(--caution);
    border-radius: calc(var(--radius) * 2);
    background: var(--caution-wash);
    font-size: var(--step--1);
  }

  h3 {
    font-size: var(--step--1);
    font-weight: 600;
  }

  p {
    margin: 0;
    color: var(--ink-soft);
  }

  pre {
    margin: 0;
    padding: 0.45rem 0.6rem;
    border-radius: var(--radius);
    background: var(--raised);
    font-size: 0.75rem;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  form,
  fieldset {
    display: grid;
    gap: 0.4rem;
  }

  fieldset {
    margin: 0;
    padding: 0;
    border: 0;
  }

  legend {
    padding: 0;
    font-weight: 600;
  }

  .option {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    cursor: pointer;
  }

  .option small {
    display: block;
    color: var(--pencil);
  }

  .answer {
    font-size: var(--step--1);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
</style>
