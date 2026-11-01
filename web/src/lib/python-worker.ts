// Runs Python for the python-run cells (ADR 0013, #136) off the page's thread, so Stop can end an endless loop by
// ending this worker. Pyodide loads from the CDN on the first run and the browser caches it; nothing ships with the app.
// Each run gets fresh globals, so cells never share variables; runs take turns.

const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';

type Pyodide = {
  globals: { get(name: string): () => unknown };
  setStdout(options: { batched: (text: string) => void }): void;
  setStderr(options: { batched: (text: string) => void }): void;
  setStdin(options: { error: boolean }): void;
  loadPackagesFromImports(code: string, options?: { messageCallback?: (message: string) => void }): Promise<unknown>;
  runPythonAsync(code: string, options?: { globals?: unknown }): Promise<unknown>;
};

export type Request = { id: number; code: string };
export type Reply =
  | { id: number; type: 'loading' | 'running' }
  | { id: number; type: 'stdout' | 'stderr'; text: string }
  | { id: number; type: 'done'; result: string | null }
  | { id: number; type: 'error'; text: string; load?: boolean };

let pyodide: Promise<Pyodide> | null = null;
let turn = Promise.resolve();
let current = 0;

const post = (reply: Reply) => postMessage(reply);

function load() {
  pyodide ??= import(/* @vite-ignore */ `${PYODIDE}pyodide.mjs`).then(async ({ loadPyodide }) => {
    const py: Pyodide = await loadPyodide({ indexURL: PYODIDE });
    // Output goes to the run in progress; input() has no keyboard here, so it fails rather than waiting forever.
    py.setStdout({ batched: (text) => post({ id: current, type: 'stdout', text: text + '\n' }) });
    py.setStderr({ batched: (text) => post({ id: current, type: 'stderr', text: text + '\n' }) });
    py.setStdin({ error: true });
    return py;
  });
  pyodide.catch(() => (pyodide = null)); // a failed load is tried again on the next run
  return pyodide;
}

/** The learner's part of a traceback: Pyodide's own frames come before the first frame in the cell (`<exec>`). */
function traceback(message: string) {
  const lines = message.split('\n');
  const first = lines.findIndex((line) => line.includes('File "<exec>"'));
  return (first > 0 ? [lines[0], ...lines.slice(first)] : lines).join('\n').trim();
}

async function run({ id, code }: Request) {
  current = id;
  let py: Pyodide;
  try {
    post({ id, type: 'loading' });
    py = await load();
  } catch (error) {
    post({ id, type: 'error', text: String((error as Error)?.message ?? error), load: true });
    return;
  }
  try {
    post({ id, type: 'running' });
    await py.loadPackagesFromImports(code, { messageCallback: () => {} });
    const result = await py.runPythonAsync(code, { globals: py.globals.get('dict')() });
    // The value of a last bare expression, as the Python prompt would show it.
    const shown = result === undefined || result === null ? null : String((result as { toString(): string }).toString());
    (result as { destroy?: () => void } | null)?.destroy?.();
    post({ id, type: 'done', result: shown });
  } catch (error) {
    post({ id, type: 'error', text: traceback(String((error as Error)?.message ?? error)) });
  }
}

onmessage = (event: MessageEvent<Request>) => {
  turn = turn.then(() => run(event.data));
};
