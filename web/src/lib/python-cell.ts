// A runnable Python cell (the `python-run` add-on, ADR 0013, #136): the fence's code in an editor with Run, Stop and
// Reset, and its output below. The editor lives in a shadow root and the element's own markup never changes, so when a
// lesson is drawn again the Markdown patcher finds an equal node and keeps it, with what the learner typed. In an
// exercise, Add to answer sends the code and its output to the answer box; the teacher assesses it like any answer.
import { t } from './i18n.svelte';
import type { Reply, Request } from './python-worker';

export const ANSWER = 'python-answer';
export type Answer = { exercise: string; text: string };

let worker: Worker | null = null;
let sequence = 0;
const listeners = new Map<number, (reply: Reply) => void>();

function python() {
  if (!worker) {
    worker = new Worker(new URL('./python-worker.ts', import.meta.url), { type: 'module' });
    worker.onmessage = (event: MessageEvent<Reply>) => listeners.get(event.data.id)?.(event.data);
  }
  return worker;
}

/** Ends every run by ending the worker; the next run starts a new one, with Pyodide from the browser's cache. */
function stopAll() {
  worker?.terminate();
  worker = null;
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
    python().postMessage({ id, code } satisfies Request);
  }

  private answer() {
    const code = this.editor.value.trim();
    const output = this.printed.trim();
    const text = '```python\n' + code + '\n```' + (output ? '\n\n' + t('Output:') + '\n```text\n' + output + '\n```' : '');
    this.dispatchEvent(new CustomEvent<Answer>(ANSWER, { bubbles: true, composed: true, detail: { exercise: this.exercise, text } }));
  }
}

if (typeof customElements !== 'undefined' && !customElements.get('python-cell')) customElements.define('python-cell', PythonCell);
