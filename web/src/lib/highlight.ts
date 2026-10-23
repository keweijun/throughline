/** Marks passages using the CSS Custom Highlight API (no DOM changes): ones the learner asked about, and their own highlights. */
const layers = { asked: new Map<string, Range[]>(), mine: new Map<string, Range[]>() };
type Layer = keyof typeof layers;

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

/**
 * Finds a passage in rendered text, ignoring whitespace differences, formulas and citation chips.
 * When the passage occurs more than once, `nearY` (a page offset) picks the occurrence closest to it.
 */
export function locate(root: HTMLElement, needle: string, nearY?: number, options: LocateOptions = {}): Range | null {
  const target = options.loose ? needle.replace(/\s+/g, '') : needle.replace(/\s+/g, ' ').trim();
  if (target.length < 3) return null;
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
  const toRange = (start: number) => {
    const [startNode, startOffset] = map[start];
    const [endNode, endOffset] = map[start + target.length - 1];
    const range = document.createRange();
    range.setStart(startNode, startOffset);
    range.setEnd(endNode, endOffset + 1);
    return range;
  };
  let start = flat.indexOf(target);
  if (start < 0) return null;
  if (nearY === undefined) return toRange(start);
  let best: Range | null = null;
  let distance = Infinity;
  for (; start >= 0; start = flat.indexOf(target, start + 1)) {
    const range = toRange(start);
    const gap = Math.abs(range.getBoundingClientRect().top + window.scrollY - nearY);
    if (gap < distance) [best, distance] = [range, gap];
  }
  return best;
}

/** Highlights each passage and returns its range (null when the passage is no longer in the text). */
export function mark(layer: Layer, key: string, root: HTMLElement, passages: string[], options?: LocateOptions): (Range | null)[] {
  const found = passages.map((p) => locate(root, p, undefined, options));
  layers[layer].set(key, found.filter((r): r is Range => r !== null));
  publish(layer);
  return found;
}

export function clear(layer: Layer, key: string) {
  layers[layer].delete(key);
  publish(layer);
}
