import { t, locale, type Language } from './i18n.svelte';
import DOMPurify from 'dompurify';
import katex from 'katex';
import { marked } from 'marked';
import type { Ref } from './types';
import { chemistryReady, drawWidgets, endsInFence, subscribe } from './widgets';
import { scrollStage, stageScroll } from './stage';

const MATH = /(```[\s\S]*?```|`[^`\n]*`)|(\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^$\n]+?)\$)/g;
const CITATION = /\[(?:Source|来源)\s+([^\s/\]]+)\s*\/\s*([^\]\s]+)\]/g;
// Structured blocks a teacher reply ends with; the host reads them and the learner never sees them.
const DECISION = /<teaching-decision>[\s\S]*$|\s*<lesson-step>[\s\S]*$/;
// The teacher's course memory note (ADR 0010), wherever it is and while it is still streaming.
const MEMORY = /\s*<(course-memory|course-change)>[\s\S]*?(<\/\1>|$)/g;

// Delimiters, by the group of MATH that holds a formula's TeX: $$…$$, \[…\], \(…\) and $…$.
const DELIMITER = { 3: 2, 4: 2, 5: 2, 6: 1 } as const;

/** The closed formulas in a text, as the renderer finds them: each one's TeX, where it sits, and whether it is display math. */
export function mathSpans(text: string) {
  const spans: { from: number; tex: string; display: boolean }[] = [];
  for (const m of text.matchAll(MATH)) {
    if (m[1] !== undefined) continue;
    const group = ([3, 4, 5, 6] as const).find((g) => m[g] !== undefined)!;
    spans.push({ from: m.index + DELIMITER[group], tex: m[group]!, display: group === 3 || group === 4 });
  }
  return spans;
}

/** Whether `pos` is inside a formula: a closed one, or one opened before it and not closed yet (as while it is typed). */
export function inMath(text: string, pos: number) {
  let last = 0;
  for (const m of text.matchAll(MATH)) {
    const end = m.index + m[0].length;
    if (m.index >= pos) break;
    if (end > pos) {
      if (m[1] !== undefined) return false;
      const group = ([3, 4, 5, 6] as const).find((g) => m[g] !== undefined)!;
      return pos >= m.index + DELIMITER[group] && pos <= end - DELIMITER[group];
    }
    last = end;
  }
  // Nothing after the last closed span is closed, so its first opener decides: code, or math still being written. An
  // inline $ only reaches to the end of its line.
  const tail = text.slice(last, pos);
  const opener = /`|\$\$|\\\[|\\\(|\$/.exec(tail);
  if (!opener || opener[0] === '`') return false;
  return opener[0] !== '$' || !tail.slice(opener.index).includes('\n');
}

function parse(text: string, breaks = false): DocumentFragment {
  const math: { tex: string; display: boolean }[] = [];
  const token = 'MATH' + crypto.randomUUID().replaceAll('-', '');
  const prepared = text.replace(MATH, (whole, code, _expr, a, b, c, d) => {
    if (code) return code;
    math.push({ tex: a ?? b ?? c ?? d, display: a !== undefined || b !== undefined });
    return token + (math.length - 1) + 'END';
  });
  const fragment = DOMPurify.sanitize(marked.parse(prepared, { async: false, breaks }) as string, {
    RETURN_DOM_FRAGMENT: true,
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['img', 'style', 'iframe', 'form', 'input', 'button', 'video', 'audio'],
    FORBID_ATTR: ['style', 'id'],
    ALLOW_DATA_ATTR: false,
  });
  replaceText(fragment, new RegExp(token + '(\\d+)END', 'g'), (match) => {
    const item = math[Number(match[1])];
    const span = document.createElement('span');
    span.dataset.tex = item.tex;
    try {
      // A chemistry formula shows as TeX until mhchem has loaded, rather than as an error.
      if (chemistryReady(item.tex)) katex.render(item.tex, span, { displayMode: item.display, throwOnError: false, trust: false, maxExpand: 1000, maxSize: 20 });
      else span.textContent = item.tex;
    } catch {
      span.textContent = item.tex;
    }
    return span;
  });
  drawWidgets(fragment, endsInFence(text), { diagram: t("Couldn't draw this diagram"), plot: t("Couldn't draw this plot") });
  markCallouts(fragment);
  // Only web links stay live, opening in a new tab; in-page anchors have no targets because ids are stripped.
  for (const link of fragment.querySelectorAll('a')) {
    const href = link.getAttribute('href') ?? '';
    if (!/^https?:\/\//i.test(href)) link.removeAttribute('href');
    else {
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
  }
  return fragment;
}

// Callout titles by language; "Note" alone would take the translation of a learner's note.
const CALLOUTS = {
  note: { en: 'Note', 'zh-CN': '说明' }, tip: { en: 'Tip', 'zh-CN': '提示' }, important: { en: 'Important', 'zh-CN': '重点' },
  warning: { en: 'Warning', 'zh-CN': '注意' }, caution: { en: 'Caution', 'zh-CN': '警告' },
} as const;

/** GitHub-style callouts: a blockquote whose first line is [!NOTE], [!TIP], [!IMPORTANT], [!WARNING] or [!CAUTION]. */
function markCallouts(fragment: DocumentFragment) {
  for (const quote of fragment.querySelectorAll('blockquote')) {
    const first = quote.firstElementChild;
    const marker = first?.tagName === 'P' ? first.firstChild : null;
    const match = marker?.nodeType === Node.TEXT_NODE ? marker.textContent!.match(/^\s*\[!(note|tip|important|warning|caution)\][ \t]*\n?/i) : null;
    if (!match) continue;
    const kind = match[1].toLowerCase() as keyof typeof CALLOUTS;
    marker!.textContent = marker!.textContent!.slice(match[0].length);
    if (marker!.nextSibling?.nodeName === 'BR') marker!.nextSibling.remove();
    if (!first!.textContent!.trim() && !first!.querySelector('*')) first!.remove();
    quote.classList.add('callout', `callout-${kind}`);
    const title = document.createElement('p');
    title.className = 'callout-title';
    title.textContent = CALLOUTS[kind][locale.language];
    quote.prepend(title);
  }
}

function replaceText(root: Node, pattern: RegExp, build: (match: RegExpExecArray) => Node, skip = 'code,pre,.katex,.widget') {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const texts: Text[] = [];
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    if (!node.parentElement?.closest(skip)) texts.push(node);
  }
  for (const node of texts) {
    const value = node.textContent ?? '';
    const result = document.createDocumentFragment();
    let last = 0;
    let match: RegExpExecArray | null;
    pattern.lastIndex = 0;
    while ((match = pattern.exec(value))) {
      result.append(value.slice(last, match.index), build(match));
      last = pattern.lastIndex;
    }
    if (last) {
      result.append(value.slice(last));
      node.replaceWith(result);
    }
  }
}

function linkCitations(fragment: DocumentFragment, refs: Ref[], onSource?: (ref: Ref) => void) {
  replaceText(fragment, CITATION, (match) => {
    const ref = refs.find((r) => r.source_id === match[1] && r.unit_id === match[2]);
    if (!ref || !onSource) {
      const pending = document.createElement('span');
      pending.className = 'citation citation-missing';
      pending.title = t('This citation does not match a registered source location');
      pending.textContent = t('source unverified');
      return pending;
    }
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'citation';
    button.dataset.ref = JSON.stringify(ref);
    button.textContent = labelFor(ref);
    button.title = t('Open the cited source');
    button.setAttribute('aria-label', t('View source {location}', { location: labelFor(ref) }));
    button.addEventListener('click', () => onSource(ref));
    return button;
  });
}

export function labelFor(ref: Ref) {
  const page = ref.unit_id.match(/^page-(\d+)$/);
  const line = ref.unit_id.match(/^line-(\d+)$/);
  return page ? t('p. {number}', { number: page[1] }) : line ? t('line {number}', { number: line[1] }) : ref.unit_id;
}

/** True when the text contains math the renderer would typeset, ignoring code. */
export function hasMath(text: string) {
  return [...text.matchAll(MATH)].some((match) => match[2] !== undefined);
}

export type MarkdownOptions = {
  language?: Language;
  text: string;
  breaks?: boolean;
  refs?: Ref[];
  onSource?: (ref: Ref) => void;
  /** The text is still streaming: re-render at most once per animation frame. */
  streaming?: boolean;
};

/** Fired on a block after the Markdown action has patched it, so overlays such as highlights can re-measure. */
export const RENDERED = 'markdown-rendered';

/** Renders sanitized Markdown, patching only changed blocks so streaming keeps selections and scroll. */
export function render(node: HTMLElement, { text, breaks = false, refs = [], onSource }: MarkdownOptions) {
  const key = locale.language + breaks + text + '\u0000' + refs.map((r) => r.source_id + r.unit_id).join();
  if (node.dataset.key === key) return;
  const fragment = parse(text.replace(MEMORY, '').replace(DECISION, ''), breaks);
  linkCitations(fragment, refs, onSource);
  const scrollY = stageScroll();
  const incoming = [...fragment.childNodes];
  incoming.forEach((child, index) => {
    const old = node.childNodes[index];
    if (!old) node.append(child);
    else if (!old.isEqualNode(child)) old.replaceWith(child);
  });
  while (node.childNodes.length > incoming.length) node.lastChild!.remove();
  node.dataset.key = key;
  if (stageScroll() !== scrollY) scrollStage(scrollY);
  node.dispatchEvent(new CustomEvent(RENDERED));
}

// Mounted Markdown and its latest options, rendered again when a widget finishes drawing or the theme changes.
const live = new Map<HTMLElement, MarkdownOptions>();
subscribe(() => {
  for (const [node, options] of live) {
    delete node.dataset.key;
    render(node, options);
  }
});

export function markdown(node: HTMLElement, options: MarkdownOptions) {
  let frame = 0;
  let latest = options;
  render(node, options);
  live.set(node, options);
  return {
    update(next: MarkdownOptions) {
      latest = next;
      live.set(node, next);
      // Streaming text arrives in many small deltas; parsing and typesetting each one would block the page.
      if (next.streaming) {
        frame ||= requestAnimationFrame(() => {
          frame = 0;
          render(node, latest);
        });
        return;
      }
      cancelAnimationFrame(frame);
      frame = 0;
      render(node, next);
    },
    destroy() {
      live.delete(node);
      cancelAnimationFrame(frame);
    },
  };
}

