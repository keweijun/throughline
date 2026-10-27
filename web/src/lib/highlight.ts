import { RENDERED } from './markdown';
import { stageOffset } from './stage';
import type { Annotation } from './types';

/** Marks passages using the CSS Custom Highlight API (no DOM changes): ones the learner asked about, and their own highlights. */

const layers = { asked: new Map<string, Range[]>(), mine: new Map<string, Range[]>() };
type Layer = keyof typeof layers;

/** A passage to paint: which of its repeats in the text (the first by default), and the annotation it belongs to. */
export type Passage = string | { text: string; occurrence?: number; id?: string };
/** The annotation each painted range belongs to, so a click on a highlight can find it. */
const owner = new WeakMap<Range, string>();

export const annotationPassage = (a: Annotation): Passage => ({ text: a.passage, occurrence: a.occurrence ?? 0, id: a.id });

function publish(layer: Layer) {
  if (!('highlights' in CSS)) return;
  const all = [...layers[layer].values()].flat();
  if (all.length) CSS.highlights.set(layer, new Highlight(...all));
  else CSS.highlights.delete(layer);
}

export type LocateOptions = {
  /** Ignore whitespace entirely, for text split into lines or PDF spans whose breaks are not in the text. */
  loose?: boolean;
  skip?: string;
};

// A passage keeps its formulas as TeX, which rendered text does not contain.
const FORMULA = /\$\$[\s\S]+?\$\$|\$[^$\n]+?\$/g;

/** Every occurrence of a passage in rendered text, ignoring whitespace differences, formulas and citation chips. */
export function occurrences(root: HTMLElement, needle: string, options: LocateOptions = {}): Range[] {
  const found = search(root, needle, options);
  return found.length || !needle.includes('$') ? found : search(root, needle.replace(FORMULA, ' '), options);
}

function search(root: HTMLElement, needle: string, options: LocateOptions): Range[] {
  const target = options.loose ? needle.replace(/\s+/g, '') : needle.replace(/\s+/g, ' ').trim();
  if (target.length < 3) return [];
  const skip = options.skip ?? '.katex, .citation';
  const nodes: Text[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.parentElement?.closest(skip) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  // Build a whitespace-collapsed copy of the text with a map back to node offsets.
  let flat = '';
  const map: [Text, number][] = [];
  for (const node of nodes) {
    const value = node.data;
    for (let i = 0; i < value.length; i++) {
      const space = /\s/.test(value[i]);
      if (space && (options.loose || flat.endsWith(' '))) continue;
      flat += space ? ' ' : value[i];
      map.push([node, i]);
    }
  }
  const ranges: Range[] = [];
  for (let start = flat.indexOf(target); start >= 0; start = flat.indexOf(target, start + 1)) {
    const [startNode, startOffset] = map[start];
    const [endNode, endOffset] = map[start + target.length - 1];
    const range = document.createRange();
    range.setStart(startNode, startOffset);
    range.setEnd(endNode, endOffset + 1);
    ranges.push(range);
  }
  return ranges;
}

/** Finds a passage in rendered text. When it occurs more than once, `nearY` (a page offset) picks the occurrence closest to it. */
export function locate(root: HTMLElement, needle: string, nearY?: number, options: LocateOptions = {}): Range | null {
  const found = occurrences(root, needle, options);
  if (nearY === undefined) return found[0] ?? null;
  let best: Range | null = null;
  let distance = Infinity;
  for (const range of found) {
    const gap = Math.abs(stageOffset(range.getBoundingClientRect().top) - nearY);
    if (gap < distance) [best, distance] = [range, gap];
  }
  return best;
}

/** Which occurrence of a passage a selection is, counted as `occurrences` counts them; 0 when it cannot tell. */
export function occurrenceOf(root: HTMLElement, needle: string, selected: Range, options?: LocateOptions): number {
  const index = occurrences(root, needle, options).findIndex(
    (range) => range.compareBoundaryPoints(Range.END_TO_START, selected) < 0 && range.compareBoundaryPoints(Range.START_TO_END, selected) > 0,
  );
  return Math.max(0, index);
}

/** Highlights each passage and returns its range (null when the passage is no longer in the text). */
export function mark(layer: Layer, key: string, root: HTMLElement, passages: Passage[], options?: LocateOptions): (Range | null)[] {
  const found = passages.map((p) => {
    const { text, occurrence = 0, id } = typeof p === 'string' ? { text: p } : p;
    const all = occurrences(root, text, options);
    // Text that changed since may have fewer repeats; the first is the best guess then.
    const range = all[occurrence] ?? all[0] ?? null;
    if (range && id) owner.set(range, id);
    return range;
  });
  layers[layer].set(key, found.filter((r): r is Range => r !== null));
  publish(layer);
  return found;
}

export function clear(layer: Layer, key: string) {
  layers[layer].delete(key);
  publish(layer);
}

/** The learner's highlight under a viewport point: its annotation and the line box hit. */
export function highlightAt(x: number, y: number): { id: string; rect: DOMRect } | null {
  for (const range of [...layers.mine.values()].flat()) {
    const id = owner.get(range);
    if (!id) continue;
    for (const rect of range.getClientRects()) {
      if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) return { id, rect };
    }
  }
  return null;
}

let nextKey = 0;

/** Svelte action: keeps the learner's highlights painted in a rendered block as its text changes. */
export function highlights(node: HTMLElement, params: { passages: Passage[]; text?: string }) {
  const key = `block-${nextKey++}`;
  let frame = 0;
  let current = params;
  const paint = (p: { passages: Passage[] }) => {
    current = p;
    cancelAnimationFrame(frame);
    // Wait for the Markdown action to finish patching this block.
    frame = requestAnimationFrame(() => mark('mine', key, node, p.passages));
  };
  // Streaming blocks are patched a frame later than their text changes; paint again once they are.
  const repaint = () => current.passages.length && mark('mine', key, node, current.passages);
  node.addEventListener(RENDERED, repaint);
  paint(params);
  return {
    update: paint,
    destroy() {
      cancelAnimationFrame(frame);
      node.removeEventListener(RENDERED, repaint);
      clear('mine', key);
    },
  };
}
