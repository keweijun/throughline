<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte';
  import { api } from '../lib/api';
  import { t, locale, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { CodexCheck, CodexChecks, DeletedCourse, LauncherStatus, LibraryCourse } from '../lib/types';
  import CodexLink from './CodexLink.svelte';
  import Studio from './Studio.svelte';
  import { studio } from '../lib/studio.svelte';
  import LauncherHelp from './LauncherHelp.svelte';
  import CourseImport from './CourseImport.svelte';
  import { lightDismiss } from '../lib/dialog';
  import { pop } from '../lib/motion';
  import InlineConfirm from './InlineConfirm.svelte';

  let opening = $state<string | null>(null);
  let launcher = $state<LauncherStatus | null>(null);
  let checks = $state<CodexCheck[]>([]);
  let checking = $state(false);

  const failing = $derived(checks.filter((check) => !check.ok));

  let poll: ReturnType<typeof setTimeout> | undefined;

  // Neither is needed to use the library, so a failure to load them shows nothing. Whether Codex answers is probed once
  // per host in the background; while it runs `checking` is true and this asks again shortly.
  async function loadChecks(again = false) {
    clearTimeout(poll);
    try {
      const view = again ? await api.post<CodexChecks>('/api/checks') : await api.get<CodexChecks>('/api/checks');
      checks = view.checks;
      checking = view.checking;
    } catch {
      checks = [];
      checking = false;
    }
    if (checking) poll = setTimeout(() => void loadChecks(), 1500);
  }

  onMount(() => {
    void loadChecks();
    api.get<LauncherStatus>('/api/launcher').then((status) => (launcher = status), () => {});
  });
  onDestroy(() => clearTimeout(poll));

  let nextTime = $state<HTMLDialogElement>();
  $effect(() => {
    // Only when there is a launcher to point to; without one, Settings → About says how to add it.
    if (launcher?.exists && !launcher.dismissed && nextTime && !nextTime.open) nextTime.showModal();
  });

  async function dismissLauncher() {
    if (!launcher || launcher.dismissed) return;
    launcher = { ...launcher, dismissed: true };
    try {
      await api.post('/api/seen', { id: 'launcher' });
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
    }
  }

  /** What failed and what to do about it; a check this version does not know is shown as the host words it. */
  function problem(check: CodexCheck) {
    if (check.id === 'codex') return [t('Codex was not found.'), t('Install Codex (the desktop app or the CLI) and sign in; lessons need it.')];
    if (check.id === 'answers') return [t('Codex could not answer:'), `${check.detail.replace(/\.$/, '')}. ${t('Check that “codex” works in a terminal (signed in, or with an API key).')}`];
    return [check.label, check.fix];
  }

  const library = $derived(app.library);
  const newCourse = $derived(t('$throughline create a new course from these files: '));

  function updated(course: LibraryCourse) {
    if (!course.updated) return '';
    return new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(course.updated * 1000));
  }

  // Studio is the way to make courses here (#109); where Codex cannot run it, the buttons open a Codex chat.
  const studioHere = $derived(!!library?.root && studio.available !== false);
  // Whether Codex can run Studio decides New course and the cards' actions, so ask once the library is known, as
  // Studio would on opening; this starts the App Server but asks no model anything.
  $effect(() => {
    if (!library?.root || studio.available !== null) return;
    untrack(() => {
      studio.setScope('library');
      void studio.load();
    });
  });

  // The page is the course list, or New course: the library's Studio across the page. With no course yet, New course
  // is the page.
  // A library whose courses are all in the trash still shows the list, so they can be restored.
  const making = $derived(studioHere && (app.libraryView === 'new' || (!!library && !library.courses.length && !library.trash?.length)));

  /** New course: the library's Studio, a new chat with the request typed in (if any) and the caret after it. */
  function ask(prompt = '') {
    app.libraryView = 'new';
    studio.newThread();
    // A new course starts clean, or with the request it was asked for.
    app.drafts.set('studio:library:new', prompt);
    studio.focusRequest++;
  }

  // A new course still being made, so leaving the chat never loses it: asked without starting Codex.
  let unfinished = $state<{ running: string[]; waiting: unknown[] } | null>(null);
  $effect(() => {
    if (!studioHere || making) return;
    api.get<{ running: string[]; waiting: unknown[] }>('/api/studio/activity?scope=library').then((a) => (unfinished = a), () => {});
  });

  /** Opens the course at its own Studio with the request filled in; one already open is handed it at once. */
  function courseStudio(name: string, prompt: string) {
    if (app.askCourseStudio(name, prompt)) {
      const handed = app.takeStudioHandoff();
      if (handed) {
        app.drafts.set('studio:new', studio.handoff(handed.prompt));
        app.showStudio({ focus: true });
      }
    } else opening = name;
  }

  // A course package to import (ADR 0020): chosen with Import course or dropped anywhere on the library. Other files
  // dropped here, on Studio, are attachments as before.
  let importing = $state<File | null>(null);
  let picker = $state<HTMLInputElement>();
  const isPackage = (file: File) => file.name.toLowerCase().endsWith('.throughline');

  function dropped(event: DragEvent) {
    const file = [...(event.dataTransfer?.files ?? [])].find(isPackage);
    if (!file || !library?.root) return;
    event.preventDefault();
    event.stopPropagation();
    app.libraryView = 'list';
    importing = file;
  }

  function dragging(event: DragEvent) {
    if (library?.root && [...(event.dataTransfer?.items ?? [])].some((item) => item.kind === 'file')) event.preventDefault();
  }

  function picked() {
    const file = picker?.files?.[0];
    if (file) {
      app.libraryView = 'list';
      importing = file;
    }
    if (picker) picker.value = '';
  }

  async function open(course: LibraryCourse) {
    opening = course.name;
    await app.openCourse(course.name);
    opening = null;
  }

  // Looking after courses (ADR 0022): rename, archive and delete sit in a small menu on each card, since they are
  // rarely used. Archived courses and the trash are folded below the list.
  const listed = $derived((library?.courses ?? []).filter((c) => !c.archived));
  const archivedCourses = $derived((library?.courses ?? []).filter((c) => c.archived));
  const trash = $derived(library?.trash ?? []);
  let showArchived = $state(false);
  let showTrash = $state(false);

  // A card's menu closes on a click outside it or on Escape, as menus do.
  let menuFor = $state<string | null>(null);
  $effect(() => {
    if (!menuFor) return;
    const away = (event: Event) => !(event.target as Element).closest?.(`[data-menu="${CSS.escape(menuFor!)}"]`) && (menuFor = null);
    const escape = (event: KeyboardEvent) => event.key === 'Escape' && (menuFor = null);
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', away);
      document.removeEventListener('keydown', escape);
    };
  });

  let renaming = $state<string | null>(null);
  let newTitle = $state('');
  let deleting = $state<string | null>(null);
  let busy = $state(false);

  // What was just archived or deleted, said where the course was, with the way back. A deleted course that was open
  // reloads every tab, so the notice waits in this tab's session storage.
  type Done = { kind: 'archived' | 'deleted'; title: string; name: string; id?: string };
  let done = $state<Done | null>(null);
  onMount(() => {
    try {
      done = JSON.parse(sessionStorage.getItem('library-done') ?? 'null');
      sessionStorage.removeItem('library-done');
    } catch {
      // Without session storage there is no notice; Deleted courses still lists the course.
    }
  });

  const label = (course: LibraryCourse) => course.title ?? course.name;

  /** Runs a library change; the listing is read again, and a refusal (a course being written in, say) floats. */
  async function change<T>(action: () => Promise<T>): Promise<T | undefined> {
    busy = true;
    app.error = null;
    try {
      const result = await action();
      await app.loadLibrary(true);
      return result;
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
      return undefined;
    } finally {
      busy = false;
    }
  }

  function startRename(course: LibraryCourse) {
    menuFor = null;
    deleting = null;
    renaming = course.name;
    newTitle = label(course);
    requestAnimationFrame(() => {
      const input = document.getElementById(`rename-${course.name}`) as HTMLInputElement | null;
      input?.focus();
      input?.select();
    });
  }

  async function rename(course: LibraryCourse) {
    if (!newTitle.trim() || busy) return;
    if (newTitle.trim() !== label(course)) {
      const renamed = await change(() => api.put(`/api/library/courses/${encodeURIComponent(course.name)}/title`, { title: newTitle }));
      if (!renamed) return;
    }
    renaming = null;
  }

  async function archive(course: LibraryCourse, archived: boolean) {
    menuFor = null;
    const result = await change(() => api.put(`/api/library/courses/${encodeURIComponent(course.name)}/archived`, { archived }));
    if (result) done = archived ? { kind: 'archived', title: label(course), name: course.name } : null;
  }

  function startDelete(course: LibraryCourse) {
    menuFor = null;
    renaming = null;
    deleting = course.name;
  }

  function stash(value: Done | null) {
    try {
      if (value) sessionStorage.setItem('library-done', JSON.stringify(value));
      else sessionStorage.removeItem('library-done');
    } catch {
      // The course is in the trash either way; only the notice is lost.
    }
  }

  async function remove(course: LibraryCourse) {
    const notice: Done = { kind: 'deleted', title: label(course), name: course.name };
    // Deleting the open course closes it, and the host reloads every tab onto the library, perhaps before the request
    // returns: the notice is kept first.
    const open = course.path === library?.active;
    if (open) stash(notice);
    const entry = await change(() => api.delete<DeletedCourse>(`/api/library/courses/${encodeURIComponent(course.name)}`));
    deleting = null;
    if (!entry) {
      if (open) stash(null);
      return;
    }
    done = { ...notice, id: entry.id };
    if (open) stash(done);  // read once the reload the host asks for has brought the library back
  }

  async function restore(id: string) {
    const restored = await change(() => api.post<{ name: string; title: string }>(`/api/library/trash/${encodeURIComponent(id)}/restore`));
    if (restored && done?.id === id) done = null;
  }

  async function undo() {
    if (!done) return;
    // After a reload the notice knows only the name: the latest deleted course of that name is the one.
    const id = done.kind === 'deleted' ? (done.id ?? trash.find((e) => e.name === done!.name)?.id) : undefined;
    if (id) await restore(id);
    else if (done.kind === 'archived') {
      const course = library?.courses.find((c) => c.name === done!.name);
      if (course) await archive(course, false);
    }
    done = null;
  }

  function deletedOn(entry: DeletedCourse) {
    return entry.deleted ? new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(entry.deleted * 1000)) : '';
  }
</script>

<section class="library" class:making aria-labelledby="library-title" ondropcapture={dropped} ondragover={dragging}>
  <input class="picker" type="file" accept=".throughline" bind:this={picker} onchange={picked} tabindex="-1" aria-hidden="true" />
  <header>
    {#if making}
      <div>
        {#if library?.courses.length}
          <button class="btn btn-quiet btn-small btn-flush back" onclick={() => (app.libraryView = 'list')}>← {t('All courses')}</button>
        {/if}
        <h1 id="library-title">{t('New course')}</h1>
      </div>
      {#if library?.root}
        <div class="header-actions">
          <button class="btn btn-small" onclick={() => picker?.click()}>{t('Import a course')}</button>
        </div>
      {/if}
    {:else}
      <div>
        <h1 id="library-title">{t('All courses')}</h1>
        {#if library?.root}<p class="root">{t('Library folder')} <code>{library.root}</code></p>{/if}
      </div>
      <div class="header-actions">
        {#if app.state}
          <button class="btn btn-small" onclick={() => (app.libraryOpen = false)}>{t('Back to {course}', { course: app.state.course.title })}</button>
        {/if}
        {#if library?.root}
          <button class="btn btn-small" onclick={() => picker?.click()}>{t('Import a course')}</button>
        {/if}
        {#if studioHere}
          <button class="btn btn-primary btn-small" onclick={() => ask()}>{t('New course')}</button>
        {:else}
          <CodexLink class="btn btn-primary btn-small" prompt={newCourse}>{t('New course in Codex')}</CodexLink>
        {/if}
      </div>
    {/if}
  </header>

  {#if failing.length}
    <div class="checks" role="alert">
      <ul>
        {#each failing as check (check.id)}
          {@const [what, fix] = problem(check)}
          <li><strong>{what}</strong> {fix}</li>
        {/each}
      </ul>
      <button class="btn btn-small" disabled={checking} onclick={() => loadChecks(true)}>{checking ? t('Checking…') : t('Check again')}</button>
    </div>
  {/if}

  <!-- Shown once, the first time the library opens after installing, as Settings is: centred, over the page. -->
  <dialog class="next-time" bind:this={nextTime} use:lightDismiss onclose={dismissLauncher} aria-labelledby="next-time-title">
    {#if launcher}
      <h2 id="next-time-title">{t('Opening Throughline next time')}</h2>
      <LauncherHelp {launcher} />
      <p class="muted later">{t('You can find this again in Settings → About.')}</p>
      <button class="btn btn-primary btn-small got-it" onclick={() => nextTime?.close()}>{t('Got it')}</button>
    {/if}
  </dialog>

  {#if importing}
    <CourseImport file={importing} onclose={() => (importing = null)} />
  {:else if making}
    <!-- New course: the library's Studio across the page (ADR 0016, #109). When the course it makes is ready, the chat
         moves into that course's own Studio by itself. -->
    <section class="studio-part" aria-label={t('Studio')}>
      <div class="frame" data-scroller>
        <Studio scope="library" />
      </div>
    </section>
  {:else if !library && app.libraryError}
    <div class="load-failed" role="alert">
      <p class="problem">{t('Your courses could not be loaded: {error}', { error: diagnostic(app.libraryError) })}</p>
      <button class="btn btn-small" onclick={() => app.retryLoad()}>{t('Try again')}</button>
    </div>
  {:else if !library}
    <p class="muted" aria-busy="true">{t('Loading your courses…')}</p>
  {:else if !library.courses.length && !library.trash?.length}
    <div class="empty">
      <h2>{t('Create your first course')}</h2>
      <ol>
        <li>{t('Choose New course in Codex, or start any Codex chat with $throughline. A chat opens with the request typed in.')}</li>
        <li>{t('Attach your PDFs or notes, or name the folder they are in, and say in a sentence what you want to learn.')}</li>
        <li>{t('Send. Codex asks a few questions about your goal and background, each with a recommended answer, proposes a route, and opens the course here when it is done.')}</li>
      </ol>
      <CodexLink class="btn btn-primary" prompt={newCourse}>{t('New course in Codex')}</CodexLink>
    </div>
  {:else}
    {#snippet card(course: LibraryCourse)}
      {@const active = course.path === library?.active}
      <li class:active class:menu-open={menuFor === course.name}>
        <div class="summary">
          {#if renaming === course.name}
            <form class="rename" onsubmit={(event) => (event.preventDefault(), void rename(course))}>
              <input
                id="rename-{course.name}"
                aria-label={t('Course title')}
                bind:value={newTitle}
                maxlength="200"
                onkeydown={(event) => event.key === 'Escape' && (renaming = null)}
              />
              <button class="btn btn-small" type="submit" disabled={busy || !newTitle.trim()}>{t('Save')}</button>
              <button class="btn btn-quiet btn-small" type="button" onclick={() => (renaming = null)}>{t('Cancel')}</button>
            </form>
          {:else}
            <h2>{label(course)}</h2>
          {/if}
          {#if course.error}
            <p class="problem">{t('This course could not be read: {error}', { error: course.error })}</p>
          {:else}
            <p class="facts">
              <span>{course.name}</span>
              <span>{t('Sources: {count}', { count: course.sources ?? 0 })}</span>
              <span>{t('Sections: {count}', { count: course.concepts ?? 0 })}</span>
              {#if updated(course)}<span>{t('Updated {date}', { date: updated(course) })}</span>{/if}
            </p>
            {#if course.goal}<p class="current">{t('Goal: {goal}', { goal: course.goal })}</p>{/if}
            {#if course.current}<p class="current">{t('Now studying: {section}', { section: course.current })}</p>{/if}
          {/if}
        </div>
        <div class="state">
          {#if course.needs_review}
            <span class="chip chip-caution">{t('{count} source locations not checked yet', { count: course.needs_review })}</span>
          {/if}
          {#if active}
            <button class="btn btn-small" onclick={() => (app.libraryOpen = false)}>{t('Continue')}</button>
          {:else if !course.error && course.concepts}
            <button class="btn btn-primary btn-small" disabled={opening !== null} onclick={() => open(course)}>
              {opening === course.name ? t('Opening…') : t('Open')}
            </button>
          {:else if !course.error}
            <span class="chip chip-plain">{t('Route not built yet')}</span>
          {/if}
          <!-- Rarely used, so kept out of sight in a small menu (ADR 0022). -->
          <div class="more" data-menu={course.name}>
            <button
              class="btn btn-quiet btn-small more-button"
              aria-haspopup="menu"
              aria-expanded={menuFor === course.name}
              aria-label={t('More actions for {course}', { course: label(course) })}
              onclick={() => (menuFor = menuFor === course.name ? null : course.name)}
            >
              <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="4.5" cy="10" r="1.5" fill="currentColor" /><circle cx="10" cy="10" r="1.5" fill="currentColor" /><circle cx="15.5" cy="10" r="1.5" fill="currentColor" /></svg>
            </button>
            {#if menuFor === course.name}
              <ul class="card-menu" role="menu" transition:pop={{ from: 'above' }} aria-label={t('More actions for {course}', { course: label(course) })}>
                {#if !course.error}
                  <li role="none"><button role="menuitem" onclick={() => startRename(course)}>{t('Rename')}</button></li>
                {/if}
                <li role="none">
                  <button role="menuitem" onclick={() => void archive(course, !course.archived)}>{course.archived ? t('Unarchive') : t('Archive')}</button>
                </li>
                <li role="none" class="danger"><button role="menuitem" onclick={() => startDelete(course)}>{t('Delete…')}</button></li>
              </ul>
            {/if}
          </div>
        </div>
        {#if !course.error && library?.root && studioHere}
          <!-- Course work asked here goes to Studio above, naming the course, as a Codex chat would. -->
          <div class="codex-actions">
            {#if !course.concepts}
              <button class="link" onclick={() => ask(t('$throughline build the route for the course {course}', { course: course.name }))}>{t('Build the route')}</button>
            {/if}
            <!-- Work on one course goes to that course's own Studio, on its Overview. -->
            <button class="link" onclick={() => courseStudio(course.name, t('$throughline add these files to the course {course}: ', { course: course.name }))}>{t('Add files')}</button>
            {#if course.needs_review}
              <button class="link" onclick={() => courseStudio(course.name, t('$throughline review the pages that still need review in the course {course}', { course: course.name }))}>{t('Check sources')}</button>
            {/if}
          </div>
        {:else if !course.error && library?.root}
          <div class="codex-actions">
            {#if !course.concepts}
              <CodexLink prompt={t('$throughline build the route for the course {course}', { course: course.name })}>{t('Build the route in Codex')}</CodexLink>
            {/if}
            <CodexLink prompt={t('$throughline add these files to the course {course}: ', { course: course.name })}>{t('Add files in Codex')}</CodexLink>
            {#if course.needs_review}
              <CodexLink prompt={t('$throughline review the pages that still need review in the course {course}', { course: course.name })}>{t('Check sources in Codex')}</CodexLink>
            {/if}
          </div>
        {/if}
        {#if deleting === course.name}
          <div class="confirm-row">
            <InlineConfirm
              danger
              {busy}
              message={t('Move “{course}” to the trash? Its progress, notes and questions go with it, and you can restore it from Deleted courses below the list.', { course: label(course) })}
              confirmLabel={t('Move to trash')}
              onconfirm={() => void remove(course)}
              oncancel={() => (deleting = null)}
            />
          </div>
        {/if}
      </li>
    {/snippet}
    {#if done}
      <!-- What was just archived or deleted, where it was, with the way back. -->
      <p class="done" role="status">
        <span>{done.kind === 'deleted' ? t('“{course}” is in the trash.', { course: done.title }) : t('“{course}” is archived.', { course: done.title })}</span>
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => void undo()}>{t('Undo')}</button>
        <button class="btn btn-quiet btn-small" aria-label={t('Dismiss')} title={t('Dismiss')} onclick={() => (done = null)}><svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" /></svg></button>
      </p>
    {/if}
    <ul class="courses">
      {#if unfinished && (unfinished.running.length || unfinished.waiting.length)}
        <!-- A new course still being made, so leaving its chat never loses it. -->
        <li class="unfinished">
          <div class="summary">
            <h2>{t('New course')}</h2>
            <p class="current">{unfinished.waiting.length ? t('Codex is waiting for your answer.') : t('Codex is making it.')}</p>
          </div>
          <div class="state">
            <button class="btn btn-primary btn-small" onclick={() => (app.libraryView = 'new')}>{t('Open the chat')}</button>
          </div>
        </li>
      {/if}
      {#each listed as course (course.path)}
        {@render card(course)}
      {/each}
    </ul>
    {#if !listed.length && archivedCourses.length}
      <p class="muted all-archived">{t('All your courses are archived.')}</p>
    {/if}

    {#if archivedCourses.length || trash.length}
      <!-- Archived courses and the trash, folded below the list. -->
      <div class="folded">
        {#if archivedCourses.length}
          <button class="btn btn-quiet btn-small btn-flush" aria-expanded={showArchived} onclick={() => (showArchived = !showArchived)}>
            {t('Archived courses ({count})', { count: archivedCourses.length })}
          </button>
        {/if}
        {#if trash.length}
          <button class="btn btn-quiet btn-small btn-flush" aria-expanded={showTrash} onclick={() => (showTrash = !showTrash)}>
            {t('Deleted courses ({count})', { count: trash.length })}
          </button>
        {/if}
      </div>
    {/if}
    {#if showArchived && archivedCourses.length}
      <section class="kept" aria-labelledby="archived-title">
        <h2 id="archived-title" class="kept-title">{t('Archived courses')}</h2>
        <p class="muted">{t('Archived courses are left out of the list. Nothing in them changes, and you can still open them.')}</p>
        <ul class="courses archived">
          {#each archivedCourses as course (course.path)}
            {@render card(course)}
          {/each}
        </ul>
      </section>
    {/if}
    {#if showTrash && trash.length}
      <section class="kept" aria-labelledby="trash-title">
        <h2 id="trash-title" class="kept-title">{t('Deleted courses')}</h2>
        <p class="muted">
          {t('Deleted courses wait in the trash until you restore them, with their progress, notes and questions. Throughline never removes them; to free the space, delete them from the trash folder yourself.')}
          {#if library.trash_folder}
            <button class="btn btn-quiet btn-small show-folder" onclick={() => void change(() => api.post('/api/library/trash/show'))}>{t('Show the trash folder')}</button>
          {/if}
        </p>
        <ul class="trash">
          {#each trash as entry (entry.id)}
            <li>
              <div>
                <strong>{entry.title ?? entry.name}</strong>
                <span class="muted">{entry.name}{#if deletedOn(entry)}{' · '}{t('Deleted {date}', { date: deletedOn(entry) })}{/if}</span>
              </div>
              <button class="btn btn-small" disabled={busy} onclick={() => void restore(entry.id)}>{t('Restore')}</button>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}

  <!-- Without a library folder, or with Studio running, there are no Codex buttons for this to explain. -->
  {#if library?.root && !studioHere}
  <aside class="codex" aria-labelledby="codex-title">
    <h2 id="codex-title">{t('Courses are built in Codex')}</h2>
    <p class="muted">{t('The Codex buttons open a new Codex chat with a $throughline request typed in. Attach your files, send, and this page updates when Codex is done.')}</p>
    <p class="muted">{t('Each Codex button also copies its request. Using the Codex CLI, or nothing opened? Paste it into Codex started in your Throughline folder.')}</p>
  </aside>
  {/if}
</section>

<style>
  /* New course: Studio across the page, on the side panel's surface and padding as on a course's Overview. */
  .studio-part .frame {
    display: flex;
    flex-direction: column;
    height: max(26rem, calc(100vh - var(--topbar) - 13rem));
    overflow-y: auto;
    /* Scrolling past the transcript's ends never carries on into the page, which would move the frame away. */
    overscroll-behavior: contain;
    padding: 1.1rem 1.1rem 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
  }

  /* New course is a page for Studio: wider than the list of courses, and one window high, so the frame reaches the
     window's foot with its writing box at the bottom whatever the window's height. */
  .library.making {
    display: flex;
    flex-direction: column;
    max-width: 76rem;
    height: calc(100dvh - var(--topbar));
    padding-bottom: 1.25rem;
  }

  .making .studio-part {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 22rem;
  }

  .making .studio-part .frame {
    flex: 1;
    height: auto;
    min-height: 0;
  }

  /* As on a course's Overview and in Codex: the chat in one centred column at a readable width, its box under it. */
  .studio-part :global(.studio > .panel-head),
  .studio-part :global(.studio > .transcript > *),
  .studio-part :global(.studio > .panel-foot) {
    width: 100%;
    max-width: 50rem;
    margin-inline: auto;
  }

  /* The page's title already names it. */
  .studio-part :global(.studio > .panel-head > .panel-bar),
  .studio-part :global(.studio > .panel-head > .panel-intro) {
    display: none;
  }

  .back {
    margin-bottom: 0.4rem;
  }

  .picker {
    display: none;
  }

  /* Looking after a course (ADR 0022): a small menu beside Open, a rename in place of the title, and inline
     confirmations and notices where the course is. */
  .more {
    position: relative;
  }

  .more-button {
    padding-inline: 0.35rem;
    color: var(--pencil);
  }

  .more-button:hover,
  .more-button[aria-expanded='true'] {
    color: var(--ink);
  }

  .courses > li.menu-open {
    position: relative;
    z-index: 2;
  }

  .card-menu {
    position: absolute;
    top: calc(100% + 0.3rem);
    right: 0;
    z-index: 50;
    display: grid;
    min-width: 11rem;
    margin: 0;
    padding: 0.3rem;
    list-style: none;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    box-shadow: var(--shadow);
  }

  .card-menu button {
    width: 100%;
    padding: 0.4rem 0.6rem;
    border: 0;
    border-radius: var(--radius);
    background: transparent;
    color: var(--ink);
    font: inherit;
    font-size: var(--step--1);
    text-align: left;
    cursor: pointer;
  }

  .card-menu button:hover,
  .card-menu button:focus-visible {
    background: var(--accent-wash);
  }

  .card-menu .danger {
    margin-top: 0.2rem;
    padding-top: 0.2rem;
    border-top: 1px solid var(--rule);
  }

  .card-menu .danger button {
    color: var(--danger);
  }

  .card-menu .danger button:hover,
  .card-menu .danger button:focus-visible {
    background: var(--danger-wash);
  }

  .rename {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
  }

  .rename input {
    flex: 1 1 14rem;
    min-width: 0;
    padding: 0.3rem 0.55rem;
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    background: var(--raised);
    color: var(--ink);
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  .confirm-row {
    flex-basis: 100%;
  }

  .done {
    animation: enter-rise var(--settle) var(--ease-out);
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.75rem;
    padding: 0.4rem 0.5rem 0.4rem 1rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    font-size: var(--step--1);
  }

  .done span {
    flex: 1;
  }

  .all-archived {
    margin-top: 0.25rem;
  }

  .folded {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 1.25rem;
    margin-top: 1.25rem;
    padding-left: 0.1rem;
  }

  .folded button {
    color: var(--pencil);
  }

  .folded button[aria-expanded='true'] {
    color: var(--ink);
  }

  .kept {
    animation: enter-rise var(--settle) var(--ease-out);
    display: grid;
    gap: 0.6rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--rule);
  }

  .kept > .muted {
    max-width: 46rem;
  }

  .kept-title {
    font-family: var(--sans);
    font-size: var(--step-0);
  }

  .courses.archived > li {
    background: transparent;
  }

  .show-folder {
    margin-left: 0.25rem;
    vertical-align: baseline;
  }

  .trash {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .trash li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.6rem 0.8rem 0.6rem 1.25rem;
    border: 1px dashed var(--rule-strong);
    border-radius: 10px;
  }

  .trash li div {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }

  .trash strong {
    font-family: var(--serif);
    font-weight: 600;
  }

  /* A new course still being made reads as a course to come, not a finished one. */
  .courses > li.unfinished {
    border-style: dashed;
    border-color: var(--accent);
    background: var(--accent-wash);
  }

  /* On a wide screen the courses sit two by two, so a library of several fits one screen. */
  @media (min-width: 64rem) {
    .library:not(.making) {
      max-width: 72rem;
    }

    .courses {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      align-items: stretch;
    }
  }

  .codex-actions .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--step--1);
    font-weight: 600;
    cursor: pointer;
  }

  .codex-actions .link:hover {
    text-decoration: underline;
  }

  .library {
    grid-column: 1 / -1;
    width: 100%;
    max-width: 52rem;
    margin-inline: auto;
    padding: 2.5rem clamp(1rem, 4vw, 3rem) 6rem;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  h1 {
    font-family: var(--serif);
    font-size: var(--step-3);
    font-weight: 600;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
  }

  .root,
  .muted,
  .facts {
    color: var(--pencil);
    font-size: var(--step--1);
    overflow-wrap: anywhere;
  }

  .courses {
    display: grid;
    gap: 0.75rem;
    padding: 0;
    list-style: none;
  }

  .courses > li:nth-child(2) {
    animation-delay: 40ms;
  }

  .courses > li:nth-child(3) {
    animation-delay: 80ms;
  }

  .courses > li:nth-child(n + 4) {
    animation-delay: 120ms;
  }

  .courses > li {
    animation: enter-rise var(--settle) var(--ease-out) backwards;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem 1.5rem;
    padding: 1rem 1.25rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
  }

  .courses > li.active {
    border-color: var(--accent);
    box-shadow: inset 3px 0 0 var(--accent);
  }

  .summary {
    min-width: 0;
    flex: 1 1 18rem;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem 0.9rem;
    margin-top: 0.2rem;
  }

  .current {
    margin-top: 0.35rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .problem {
    color: var(--danger);
    font-size: var(--step--1);
  }

  .load-failed {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem 1rem;
  }

  .load-failed .problem {
    margin: 0;
  }

  .codex-actions {
    flex-basis: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 1.1rem;
    padding-top: 0.6rem;
    border-top: 1px solid var(--rule);
    font-size: var(--step--1);
  }

  .state {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem;
  }

  .empty {
    animation: enter-rise var(--settle) var(--ease-out);
    display: grid;
    justify-items: start;
    gap: 0.9rem;
    padding: 1.5rem 1.5rem 1.75rem;
    border: 1px dashed var(--rule-strong);
    border-radius: 10px;
  }

  .empty ol {
    display: grid;
    gap: 0.45rem;
    padding-left: 1.25rem;
    color: var(--ink-soft);
  }

  .checks {
    animation: enter-rise var(--settle) var(--ease-out);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem 1.5rem;
    margin-bottom: 1rem;
    padding: 0.85rem 1.25rem;
    border: 1px solid var(--caution);
    border-radius: 10px;
    background: var(--caution-wash);
  }

  .checks ul {
    display: grid;
    gap: 0.3rem;
    flex: 1 1 24rem;
    padding: 0;
    list-style: none;
    font-size: var(--step--1);
  }

  .checks strong {
    color: var(--caution);
    font-weight: 600;
  }

  .next-time {
    width: min(34rem, calc(100vw - 2rem));
    padding: 1.4rem 1.5rem 1.25rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
  }

  .next-time::backdrop {
    background: rgb(17 20 27 / 0.45);
  }

  .next-time h2 {
    margin-bottom: 0.6rem;
    font-size: var(--step-1);
    font-family: var(--sans);
  }

  .got-it {
    display: block;
    margin: 1.1rem 0 0 auto;
  }

  .later {
    margin-top: 0.6rem;
  }

  .codex {
    margin-top: 2.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--rule);
  }

  .codex h2 {
    font-size: var(--step-0);
    font-family: var(--sans);
  }

  /* Switching between the list and a new course brings the other in rather than swapping it in a blink; a fade, so
     Studio's box never moves under a learner already typing in it. */
  .studio-part,
  header > div {
    animation: enter-fade var(--settle) ease;
  }
</style>
