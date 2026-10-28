import { RENDERED } from './markdown';
import { stageOffset } from './stage';
import type { Annotation } from './types';

/**
 * Marks passages the learner asked about, and their own highlights: text through the CSS Custom Highlight API, so the
 * text is never rewrapped, and a whole formula through an attribute on its element.
 */

const layers = { asked: new Map<string, Range[]>(), mine: new Map<string, Range[]>() };
type Layer = keyof typeof layers;

/** A passage to paint: which of its repeats in the text (the first by default), and the annotation it belongs to. */
export type Passage = string | { text: string; occurrence?: number; id?: string };
/** The annotation each painted range belongs to, so a click on a highlight can find it. */
const owner = new WeakMap<Range, string>();

export const annotationPassage = (a: Annotation): Passage => ({ text: a.passage, occurrence: a.occurrence ?? 0, id: a.id });

// A rendered formula is a `[data-tex]` element holding KaTeX's glyph boxes. Painting those one by one leaves a patchy
// highlight, so a formula inside a passage is marked whole with an attribute the stylesheet paints, and only the text
// around it goes to the highlight registry.
const FORMULA_ELEMENT = '[data-tex]';
const formulaAttribute = (layer: Layer) => `data-highlight-${layer}`;
const markedFormulas = { asked: new Set<Element>(), mine: new Set<Element>() };

/** The formulas a range covers, and the text pieces between them. */
function split(range: Range): { pieces: Range[]; formulas: Element[] } {
  const scope = range.commonAncestorContainer;
  const root = scope instanceof Element ? scope : scope.parentElement;
  const inside = root?.closest(FORMULA_ELEMENT);
  if (inside) return { pieces: [], formulas: [inside] };
  const formulas = [...(root?.querySelectorAll(FORMULA_ELEMENT) ?? [])].filter((f) => range.intersectsNode(f));
  if (!formulas.length) return { pieces: [range], formulas };
  const pieces: Range[] = [];
  let piece = range.cloneRange();
  for (const formula of formulas) {
    piece.setEndBefore(formula);
    if (!piece.collapsed) pieces.push(piece);
    piece = range.cloneRange();
    piece.setStartAfter(formula);
  }
  if (!piece.collapsed) pieces.push(piece);
  return { pieces, formulas };
}

function publish(layer: Layer) {
  const parts = [...layers[layer].values()].flat().map(split);
  const formulas = new Set(parts.flatMap((p) => p.formulas));
  const attribute = formulaAttribute(layer);
  for (const formula of markedFormulas[layer]) if (!formulas.has(formula)) formula.removeAttribute(attribute);
  for (const formula of formulas) formula.setAttribute(attribute, '');
  markedFormulas[layer] = formulas;
  if (!('highlights' in CSS)) return;
  const pieces = parts.flatMap((p) => p.pieces);
  if (pieces.length) CSS.highlights.set(layer, new Highlight(...pieces));
  else CSS.highlights.delete(layer);
}

export type LocateOptions = {
  /** Ignore whitespace entirely, for text split into lines or PDF spans whose breaks are not in the text. */
  loose?: boolean;
  skip?: string;
};

// A passage keeps its formulas as TeX ($…$ or $$…$$), as the selection recorded them.
const FORMULA = /\$\$[\s\S]+?\$\$|\$[^$\n]+?\$/g;
// In the text searched, a formula stands as its TeX between two markers that ordinary text never contains.
const token = (tex: string) => `\u0001${tex.replace(/\s+/g, '')}\u0002`;
const tokenize = (needle: string) => needle.replace(FORMULA, (m) => token(m.startsWith('$$') ? m.slice(2, -2) : m.slice(1, -1)));

/**
 * Every occurrence of a passage in rendered text, ignoring whitespace differences and citation chips. A formula in the
 * passage matches the rendered formula with the same TeX; passages saved from text whose formulas differ since are
 * matched on their words alone.
 */
export function occurrences(root: HTMLElement, needle: string, options: LocateOptions = {}): Range[] {
  const found = search(root, tokenize(needle), options, true);
  return found.length || !needle.includes('$') ? found : search(root, needle.replace(FORMULA, ' '), options, false);
}

type Position = [Text, number] | Element;

function search(root: HTMLElement, needle: string, options: LocateOptions, formulas: boolean): Range[] {
  const target = options.loose ? needle.replace(/\s+/g, '') : needle.replace(/\s+/g, ' ').trim();
  if (target.length < 3) return [];
  const skip = options.skip ?? '.katex, .citation';
  const nodes: (Text | Element)[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
    acceptNode: (node) => {
      const parent = node.parentElement;
      if (parent?.closest(FORMULA_ELEMENT)) return NodeFilter.FILTER_REJECT;
      if (node instanceof Element) {
        if (node.matches(FORMULA_ELEMENT)) return formulas ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        return node.matches(skip) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
      }
      return parent?.closest(skip) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
    },
  });
  while (walker.nextNode()) nodes.push(walker.currentNode as Text | Element);
  // Build a whitespace-collapsed copy of the text with a map back to node offsets, or to the formula a token stands for.
  let flat = '';
  const map: Position[] = [];
  for (const node of nodes) {
    if (node instanceof Element) {
      const text = token((node as HTMLElement).dataset.tex ?? '');
      flat += text;
      for (let i = 0; i < text.length; i++) map.push(node);
      continue;
    }
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
    const first = map[start];
    const last = map[start + target.length - 1];
    const range = document.createRange();
    if (first instanceof Element) range.setStartBefore(first);
    else range.setStart(first[0], first[1]);
    if (last instanceof Element) range.setEndAfter(last);
    else range.setEnd(last[0], last[1] + 1);
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
