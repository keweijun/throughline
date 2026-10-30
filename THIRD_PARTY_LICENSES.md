# Bundled frontend dependencies

The MIT license at the repository root covers this project's own code. The built interface includes code and fonts from the packages below, which retain their respective licenses. These license texts are copied from the versions pinned in `web/package-lock.json`:

| Package | Version checked | License | Included text |
| --- | --- | --- | --- |
| `@fontsource-variable/source-serif-4` | 5.3.1 | OFL-1.1 | [`licenses/source-serif-4.LICENSE`](licenses/source-serif-4.LICENSE) |
| `@fontsource/ibm-plex-sans` | 5.3.0 | OFL-1.1 | [`licenses/ibm-plex-sans.LICENSE`](licenses/ibm-plex-sans.LICENSE) |
| `dompurify` | 3.4.17 | MPL-2.0 OR Apache-2.0 | [`licenses/dompurify.LICENSE`](licenses/dompurify.LICENSE), [`LICENSE-MPL`](licenses/dompurify.LICENSE-MPL) |
| `highlight.js` | 11.12.0 | BSD-3-Clause | [`licenses/highlight.js.LICENSE`](licenses/highlight.js.LICENSE) |
| `katex` | 0.19.0 | MIT | [`licenses/katex.LICENSE`](licenses/katex.LICENSE) |
| `marked` | 18.1.1 | MIT | [`licenses/marked.LICENSE`](licenses/marked.LICENSE) |
| `mermaid` | 12.2.0 | MIT | [`licenses/mermaid.LICENSE`](licenses/mermaid.LICENSE) |
| `mermaid` dependencies (d3, cytoscape, chevrotain, dagre-d3-es, roughjs and others) | as locked | MIT, ISC, BSD-3-Clause, Apache-2.0, Unlicense | [`licenses/mermaid-dependencies.LICENSE`](licenses/mermaid-dependencies.LICENSE) |
| `pdfjs-dist` | 6.4.299 | Apache-2.0 | [`licenses/pdfjs-dist.LICENSE`](licenses/pdfjs-dist.LICENSE) |

Mermaid's optional ELK layout (`elkjs`, EPL-2.0) is not shipped: the build replaces it with Mermaid's default layout (`web/vite.config.ts`).

When frontend dependencies change, update the versions and copied notices alongside the rebuilt `guided_learning/web_dist` assets.
