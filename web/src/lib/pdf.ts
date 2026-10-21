import type { PDFDocumentProxy } from 'pdfjs-dist/legacy/build/pdf.mjs';
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url';

export type PdfModule = typeof import('pdfjs-dist/legacy/build/pdf.mjs');

let module: Promise<PdfModule> | null = null;
const documents = new Map<string, Promise<PDFDocumentProxy>>();

/** pdf.js is loaded on first use so the reading view stays light. */
export function pdfjs(): Promise<PdfModule> {
  module ??= import('pdfjs-dist/legacy/build/pdf.mjs').then((pdf) => {
    pdf.GlobalWorkerOptions.workerSrc = workerUrl;
    return pdf;
  });
  return module;
}

/** Revisions are immutable, so a loaded document can be reused for every citation into it. */
export function openPdf(url: string): Promise<PDFDocumentProxy> {
  let doc = documents.get(url);
  if (!doc) {
    doc = pdfjs().then((pdf) => pdf.getDocument({ url }).promise);
    doc.catch(() => documents.delete(url));
    documents.set(url, doc);
  }
  return doc;
}
