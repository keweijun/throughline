// Teaching widgets (ADR 0013): fenced code blocks drawn as diagrams, plots or highlighted code, and chemistry in
// formulas. Every widget renders in every course; a course's add-on selection only changes what the teacher is told.
// Libraries load on first use, so a course that never draws a diagram never downloads Mermaid. Drawing is synchronous
// from caches: when a library or an asynchronous drawing becomes ready, subscribers render again.
import DOMPurify from 'dompurify';
import { locale } from './i18n.svelte';
import { drawPlot } from './plot';
import './python-cell';

type HighlightJs = typeof import('highlight.js').default;
type Mermaid = typeof import('mermaid').default;

const listeners = new Set<() => void>();
let queued = 0;

/** Calls `listener` when drawings that were pending are ready, or the theme changes; returns an unsubscribe function. */
export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function changed() {
  queued ||= requestAnimationFrame(() => {
    queued = 0;
    for (const listener of listeners) listener();
  });
}

function loader<T>(load: () => Promise<T>) {
  let value: T | undefined;
  let started = false;
  return () => {
    if (!started) {
      started = true;
      load().then((loaded) => {
        value = loaded;
        changed();
      }, (error) => console.error('A widget library failed to load', error));
    }
    return value;
  };
}

const highlighter = loader<HighlightJs>(() => import('highlight.js/lib/common').then((m) => m.default));
const mermaidLibrary = loader<Mermaid>(() => import('mermaid').then((m) => m.default));
const mhchem = loader(() => import('katex/contrib/mhchem').then(() => true));

/** True once mhchem is ready for `tex`; until then a formula using \ce or \pu waits for it. */
export function chemistryReady(tex: string) {
  return !/\\(ce|pu)\b/.test(tex) || mhchem() === true;
}

export function scheme(): 'light' | 'dark' {
  const theme = document.documentElement.dataset.theme;
  return theme === 'dark' || (theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
}

if (typeof window !== 'undefined') {
  new MutationObserver(changed).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', changed);
}

/** A theme color as the browser resolves it, so Mermaid can compute shades from it. */
function color(variable: string) {
  const probe = document.createElement('span');
  probe.style.color = `var(${variable})`;
  document.body.append(probe);
  const value = getComputedStyle(probe).color;
  probe.remove();
  return value;
}

type Drawing = { svg: string } | { error: string };
const diagrams = new Map<string, Drawing>();
const DIAGRAM_CACHE = 200;
let rendering = Promise.resolve();
let sequence = 0;

function diagram(source: string): Drawing | undefined {
  const mermaid = mermaidLibrary();
  const key = scheme() + '\u0000' + source;
  const known = diagrams.get(key);
  if (known || !mermaid) return known;
  diagrams.set(key, { error: '' }); // drawing: shown as source until ready, never queued twice
  rendering = rendering.then(async () => {
    let drawing: Drawing;
    try {
      mermaid.initialize({
        startOnLoad: false, securityLevel: 'strict', suppressErrorRendering: true, theme: 'base', htmlLabels: false,
        fontFamily: getComputedStyle(document.body).fontFamily,
        themeVariables: {
          darkMode: scheme() === 'dark', fontSize: '15px', background: color('--sheet'), primaryColor: color('--accent-wash'),
          primaryTextColor: color('--ink'), primaryBorderColor: color('--accent'), secondaryColor: color('--raised'),
          tertiaryColor: color('--ground'), lineColor: color('--pencil'), textColor: color('--ink'), noteBkgColor: color('--caution-wash'),
          noteTextColor: color('--ink'), noteBorderColor: color('--caution'), edgeLabelBackground: color('--sheet'),
        },
      });
      const { svg } = await mermaid.render(`diagram-${++sequence}`, source);
      drawing = { svg: DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true }, ADD_TAGS: ['style'] }) };
    } catch (error) {
      drawing = { error: String((error as Error)?.message ?? error).split('\n')[0].replace(/:$/, '') };
    }
    if (diagrams.size >= DIAGRAM_CACHE) diagrams.delete(diagrams.keys().next().value!);
    diagrams.set(key, drawing);
    changed();
  });
  return undefined;
}

function failed(kind: string, source: string, detail: string, note: string) {
  const box = document.createElement('div');
  box.className = `widget widget-${kind} widget-failed`;
  const message = document.createElement('p');
  message.className = 'widget-note';
  message.textContent = detail ? `${note} (${detail})` : note;
  const pre = document.createElement('pre');
  pre.textContent = source;
  box.append(message, pre);
  return box;
}

function figure(kind: string, html: string) {
  const box = document.createElement('div');
  box.className = `widget widget-${kind}`;
  box.innerHTML = html;
  return box;
}

export type Notes = { diagram: string; plot: string };

/**
 * Replaces each finished fenced code block in `root` with its widget: a Mermaid diagram, a plot, or highlighted code.
 * `open` is true when the text ends inside a fence that is still streaming; its block stays plain until it closes.
 */
export function drawWidgets(root: DocumentFragment, open: boolean, notes: Notes) {
  const blocks = [...root.querySelectorAll('pre > code')];
  blocks.forEach((code, index) => {
    const pre = code.parentElement!;
    const language = [...code.classList].find((c) => c.startsWith('language-'))?.slice(9).toLowerCase() ?? '';
    const source = code.textContent ?? '';
    const streaming = open && index === blocks.length - 1;
    if (language === 'mermaid') {
      if (streaming) return;
      const drawing = diagram(source.trim());
      if (drawing && 'svg' in drawing) pre.replaceWith(figure('diagram', drawing.svg));
      else if (drawing?.error) pre.replaceWith(failed('diagram', source, drawing.error, notes.diagram));
    } else if (language === 'plot') {
      if (streaming) return;
      try {
        pre.replaceWith(figure('plot', drawPlot(source)));
      } catch (error) {
        pre.replaceWith(failed('plot', source, (error as Error).message, notes.plot));
      }
    } else if (language === 'python-run') {
      if (streaming) return;
      // The cell keeps its editor in a shadow root; the language attribute redraws its labels when the language changes.
      const cell = document.createElement('python-cell');
      cell.setAttribute('source', source.replace(/\n$/, ''));
      cell.setAttribute('data-language', locale.language);
      pre.replaceWith(cell);
    } else if (language && language !== 'text' && language !== 'plaintext') {
      const hljs = highlighter();
      if (!hljs) return;
      if (!hljs.getLanguage(language)) return;
      // highlight.js escapes the source; its markup is only spans with token classes.
      code.innerHTML = hljs.highlight(source, { language, ignoreIllegals: true }).value;
      code.classList.add('hljs');
    }
  });
}

/** True when `text` ends inside an unclosed ``` or ~~~ fence. */
export function endsInFence(text: string) {
  let fence: string | null = null;
  for (const line of text.split('\n')) {
    const match = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (!match) continue;
    if (fence === null) fence = match[1];
    else if (match[1][0] === fence[0] && match[1].length >= fence.length && !line.slice(line.indexOf(match[1]) + match[1].length).trim()) fence = null;
  }
  return fence !== null;
}
