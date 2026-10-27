/**
 * The reading column scrolls inside the stage rather than the window, so its scrollbar sits beside the side panel
 * instead of past it. Offsets here are measured in the stage's content, like `window.scrollY` was for the page.
 */
export function stage() {
  return document.getElementById('stage');
}

export function stageScroll() {
  return stage()?.scrollTop ?? 0;
}

export function scrollStage(top: number, behavior: ScrollBehavior = 'instant') {
  stage()?.scrollTo({ top, behavior });
}

/** The visible height of the reading column. */
export function stageHeight() {
  return stage()?.clientHeight ?? window.innerHeight;
}

/** Converts a viewport y (such as a bounding rectangle's top) to an offset in the stage's content. */
export function stageOffset(clientY: number) {
  const el = stage();
  return el ? clientY - el.getBoundingClientRect().top + el.scrollTop : clientY + window.scrollY;
}

/**
 * With nothing focused the browser would scroll the window, which no longer moves; the keys that scroll a page
 * scroll the stage instead. Returns whether the key was handled.
 */
export function scrollStageByKey(event: KeyboardEvent) {
  const el = stage();
  if (!el || event.target !== document.body || event.metaKey || event.ctrlKey || event.altKey) return false;
  const page = el.clientHeight * 0.9;
  const by: Record<string, number> = {
    ArrowDown: 48,
    ArrowUp: -48,
    PageDown: page,
    PageUp: -page,
    ' ': event.shiftKey ? -page : page,
    Home: -el.scrollHeight,
    End: el.scrollHeight,
  };
  if (!(event.key in by)) return false;
  event.preventDefault();
  el.scrollBy({ top: by[event.key], behavior: event.key.startsWith('Arrow') ? 'instant' : 'smooth' });
  return true;
}
