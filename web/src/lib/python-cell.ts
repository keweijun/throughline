// A runnable Python cell (the `python-run` add-on, ADR 0013, #136): the fence's code in an editor with Run, Stop and
// Reset, and its output below. The editor lives in a shadow root and the element's own markup never changes, so when a
// lesson is drawn again the Markdown patcher finds an equal node and keeps it, with what the learner typed. In an
// exercise, Add to answer sends the code and its output to the answer box; the teacher assesses it like any answer.
import { t } from './i18n.svelte';
import type { Reply, Request } from './python-worker';
import workerUrl from './python-worker.ts?worker&url';

export const ANSWER = 'python-answer';
export type Answer = { exercise: string; text: string };

// The worker runs inside a sandboxed frame with no origin of its own, so a cell's requests are not the app's: the host
// refuses them as it refuses any other site's. The frame cannot load the app's files, so the page hands it the worker's
// code, and starts it as a data URL: Pyodide needs a module worker, and a frame without an origin cannot start one from a
// blob. After that the frame only passes messages between the page and the worker.
const FRAME = `<script>
let worker;
onmessage = (event) => {
  if (event.source !== parent) return;
  if (worker) return worker.postMessage(event.data);
  worker = new Worker('data:text/javascript,' + encodeURIComponent(event.data), { type: 'module' });
  worker.onmessage = (reply) => parent.postMessage(reply.data, '*');
};
</script>`;

let frame: HTMLIFrameElement | null = null;
let ready: Promise<Window> | null = null;
let sequence = 0;
const listeners = new Map<number, (reply: Reply) => void>();

function python() {
  if (!ready) {
    const box = (frame = document.createElement('iframe'));
    box.sandbox.add('allow-scripts');
    box.srcdoc = FRAME;
    box.hidden = true;
    box.tabIndex = -1;
    box.setAttribute('aria-hidden', 'true');
    const loaded = new Promise((resolve) => box.addEventListener('load', resolve, { once: true }));
    const started = (ready = Promise.all([fetch(workerUrl).then((response) => response.text()), loaded]).then(([source]) => {
      box.contentWindow!.postMessage(source, '*');
      return box.contentWindow!;
    }));
    started.catch(() => {
      box.remove();
      if (ready === started) ready = frame = null; // tried again on the next run
    });
    document.body.append(box);
  }
  return ready;
}

/** A reply from the frame: only the shapes the worker sends are read, and only as text. */
function reply(data: unknown): data is Reply {
  const value = data as Partial<Record<'id' | 'type' | 'text' | 'result', unknown>> | null;
  return typeof value?.id === 'number' && typeof value.type === 'string' && ['undefined', 'string'].includes(typeof value.text) &&
    (value.result === undefined || value.result === null || typeof value.result === 'string');
}

if (typeof window !== 'undefined') {
  addEventListener('message', (event) => {
    if (frame && event.source === frame.contentWindow && reply(event.data)) listeners.get(event.data.id)?.(event.data);
  });
}

/** Ends every run by removing the frame, and the worker with it; the next run starts both again, with Pyodide from the
 * browser's cache. */
function stopAll() {
  frame?.remove();
  frame = null;
  ready = null;
  for (const [id, listener] of listeners) listener({ id, type: 'error', text: '' });
  listeners.clear();
}

const STYLE = `
  :host { display: block; margin: 1rem 0; }
  .cell { border: 1px solid var(--rule); border-radius: var(--radius, 6px); background: var(--sheet); overflow: hidden; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.3rem 0.4rem 0.3rem 0.7rem;
    border-bottom: 1px solid var(--rule); background: var(--raised); color: var(--pencil); font-size: 0.8em; }
  textarea { display: block; box-sizing: border-box; width: 100%; margin: 0; padding: 0.6rem 0.7rem; border: 0; resize: vertical;
    background: transparent; color: var(--ink); font: 0.9em/1.5 var(--mono, monospace); tab-size: 4; white-space: pre; overflow-x: auto; }
  textarea:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .actions { display: flex; flex-wrap: wrap; gap: 0.3rem; padding: 0.4rem; border-top: 1px solid var(--rule); }
  button { font: inherit; font-size: 0.85em; padding: 0.25rem 0.7rem; border: 1px solid var(--rule); border-radius: var(--radius, 6px);
    background: var(--sheet); color: var(--ink); cursor: pointer; }
  button:hover:not(:disabled) { border-color: var(--pencil); }
  button:disabled { opacity: 0.5; cursor: default; }
  button.run { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
  button.run:hover:not(:disabled) { background: var(--accent-hover); border-color: var(--accent-hover); }
  button.quiet { border-color: transparent; background: transparent; color: var(--pencil); }
  .output { margin: 0; padding: 0.6rem 0.7rem; border-top: 1px solid var(--rule); background: var(--ground);
    color: var(--ink); font: 0.85em/1.5 var(--mono, monospace); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 24rem; overflow: auto; }
  .output:empty { display: none; }
  .status { color: var(--pencil); font-style: italic; }
  .stderr, .error { color: var(--caution, #b45309); }
`;

class PythonCell extends HTMLElement {
  private editor!: HTMLTextAreaElement;
  private output!: HTMLPreElement;
  private runButton!: HTMLButtonElement;
  private stopButton!: HTMLButtonElement;
  private answerButton!: HTMLButtonElement;
  private run = 0;
  private printed = '';

  connectedCallback() {
    if (this.shadowRoot) return; // moved, not new: keep the editor and output
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `<style>${STYLE}</style><div class="cell"><div class="head"><span></span><button class="quiet reset"></button></div>
      <textarea spellcheck="false" autocapitalize="off" autocomplete="off"></textarea>
      <div class="actions"><button class="run"></button><button class="stop" disabled></button><button class="answer"></button></div>
      <pre class="output" aria-live="polite"></pre></div>`;
    const starter = this.getAttribute('source') ?? '';
    root.querySelector('.head span')!.textContent = t('Python');
    const reset = root.querySelector<HTMLButtonElement>('.reset')!;
    reset.textContent = t('Reset');
    reset.title = t('Put back the original code');
    this.editor = root.querySelector('textarea')!;
    this.editor.setAttribute('aria-label', t('Python code'));
    this.editor.value = starter;
    this.output = root.querySelector('.output')!;
    this.runButton = root.querySelector('.run')!;
    this.runButton.textContent = t('Run');
    this.runButton.title = t('Run (Ctrl+Enter)');
    this.stopButton = root.querySelector('.stop')!;
    this.stopButton.textContent = t('Stop');
    this.answerButton = root.querySelector('.answer')!;
    this.answerButton.textContent = t('Add to answer');
    this.answerButton.hidden = !this.exercise;
    this.fit();

    this.editor.addEventListener('input', () => this.fit());
    // Keys typed here are the learner's code, not the app's shortcuts, which look at the event outside this root.
    this.editor.addEventListener('keydown', (event) => {
      event.stopPropagation();
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        this.start();
      } else if (event.key === 'Tab' && !event.shiftKey) {
        event.preventDefault();
        this.editor.setRangeText('    ', this.editor.selectionStart, this.editor.selectionEnd, 'end');
        this.fit();
      }
    });
    this.runButton.addEventListener('click', () => this.start());
    this.stopButton.addEventListener('click', () => stopAll());
    reset.addEventListener('click', () => {
      this.editor.value = starter;
      this.output.replaceChildren();
      this.printed = '';
      this.fit();
    });
    this.answerButton.addEventListener('click', () => this.answer());
  }

  /** The exercise this cell is part of, when it is in an exercise's question. */
  private get exercise() {
    return this.closest<HTMLElement>('[data-exercise]')?.dataset.exercise ?? '';
  }

  private fit() {
    this.editor.rows = Math.min(30, Math.max(3, this.editor.value.split('\n').length));
  }

  private line(text: string, kind: 'status' | 'stdout' | 'stderr' | 'error' | 'result') {
    if (kind === 'status') {
      const span = document.createElement('span');
      span.className = 'status';
      span.textContent = text;
      this.output.replaceChildren(span);
      return;
    }
    this.output.querySelector('.status')?.remove();
    const span = document.createElement('span');
    span.className = kind;
    span.textContent = text;
    this.output.append(span);
    if (kind !== 'error') this.printed += text;
  }

  private start() {
    const code = this.editor.value;
    const id = (this.run = ++sequence);
    this.printed = '';
    this.runButton.disabled = true;
    this.stopButton.disabled = false;
    const finish = () => {
      listeners.delete(id);
      if (this.run !== id) return;
      this.runButton.disabled = false;
      this.stopButton.disabled = true;
    };
    listeners.set(id, (reply) => {
      if (this.run !== id) return;
      if (reply.type === 'loading') this.line(t('Loading Python…'), 'status');
      else if (reply.type === 'running') this.line(t('Running…'), 'status');
      else if (reply.type === 'stdout' || reply.type === 'stderr') this.line(reply.text, reply.type);
      else if (reply.type === 'done') {
        if (reply.result !== null) this.line(reply.result + '\n', 'result');
        if (!this.output.textContent) this.line(t('Finished with no output.'), 'status');
        finish();
      } else if (reply.type === 'error') {
        if (reply.load) this.line(t("Python could not load. Check your connection and run again."), 'error');
        else this.line(reply.text || t('Stopped.'), reply.text ? 'error' : 'status');
        finish();
      }
    });
    python().then(
      (box) => box.postMessage({ id, code } satisfies Request, '*'),
      () => listeners.get(id)?.({ id, type: 'error', text: '', load: true }),
    );
  }

  private answer() {
    const code = this.editor.value.trim();
    const output = this.printed.trim();
    const text = '```python\n' + code + '\n```' + (output ? '\n\n' + t('Output:') + '\n```text\n' + output + '\n```' : '');
    this.dispatchEvent(new CustomEvent<Answer>(ANSWER, { bubbles: true, composed: true, detail: { exercise: this.exercise, text } }));
  }
}

if (typeof customElements !== 'undefined' && !customElements.get('python-cell')) customElements.define('python-cell', PythonCell);
