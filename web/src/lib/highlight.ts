/** Marks passages the learner asked about, using the CSS Custom Highlight API (no DOM changes). */
const ranges = new Map<string, Range[]>();

function publish() {
  if (!('highlights' in CSS)) return;
  const all = [...ranges.values()].flat();
  if (all.length) CSS.highlights.set('asked', new Highlight(...all));
  else CSS.highlights.delete('asked');
}

function find(root: HTMLElement, needle: string): Range | null {
  const target = needle.replace(/\s+/g, ' ').trim();
  if (target.length < 3) return null;
  const nodes: Text[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (node.parentElement?.closest('.katex, .citation') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  // Build a whitespace-collapsed copy of the text with a map back to node offsets.
  let flat = '';
  const map: [Text, number][] = [];
  for (const node of nodes) {
    const value = node.data;
    for (let i = 0; i < value.length; i++) {
      const space = /\s/.test(value[i]);
      if (space && flat.endsWith(' ')) continue;
      flat += space ? ' ' : value[i];
      map.push([node, i]);
    }
  }
  const start = flat.indexOf(target);
  if (start < 0) return null;
  const [startNode, startOffset] = map[start];
  const [endNode, endOffset] = map[start + target.length - 1];
  const range = document.createRange();
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset + 1);
  return range;
}

/** Highlights each passage and returns its range (null when the passage is no longer in the text). */
export function markAsked(key: string, root: HTMLElement, passages: string[]): (Range | null)[] {
  const found = passages.map((p) => find(root, p));
  ranges.set(key, found.filter((r): r is Range => r !== null));
  publish();
  return found;
}

export function clearAsked(key: string) {
  ranges.delete(key);
  publish();
}
