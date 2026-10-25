import type { PDFDocumentProxy } from 'pdfjs-dist/legacy/build/pdf.mjs';
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url';

export type PdfModule = typeof import('pdfjs-dist/legacy/build/pdf.mjs');

let module: Promise<PdfModule> | null = null;
/** Recently opened documents, least recently used first. */
const documents = new Map<string, Promise<PDFDocumentProxy>>();
/** Going back and forth between a few sources stays instant; older documents release their memory. */
const KEEP = 3;

/** pdf.js is loaded on first use so the reading view stays light. */
export function pdfjs(): Promise<PdfModule> {
  module ??= import('pdfjs-dist/legacy/build/pdf.mjs').then((pdf) => {
    pdf.GlobalWorkerOptions.workerSrc = workerUrl;
    return pdf;
  });
  return module;
}

/** Revisions are immutable, so a loaded document can be reused for every citation into it; `key` names the file. */
export function openPdf(url: string, key = url): Promise<PDFDocumentProxy> {
  let doc = documents.get(key);
  if (doc) documents.delete(key);
  else {
    doc = pdfjs().then((pdf) => pdf.getDocument({ url }).promise);
    doc.catch(() => documents.get(key) === doc && documents.delete(key));
  }
  documents.set(key, doc);

  for (const [old, evicted] of documents) {
    if (documents.size <= KEEP) break;
    documents.delete(old);
    evicted.then((d) => d.loadingTask.destroy()).catch(() => {});
  }
  return doc;
}
