import { defineConfig } from 'vite';
import { readdirSync } from 'node:fs';
import path from 'node:path';
import { svelte } from '@sveltejs/vite-plugin-svelte';

const host = process.env.GL_HOST ?? 'http://127.0.0.1:8765';

// Every supported browser loads WOFF2, so legacy font formats only bloat the package.
const woff2Only = {
  name: 'woff2-only',
  enforce: 'pre' as const,
  transform(code: string, id: string) {
    if (!/katex|@fontsource/.test(id) || !id.endsWith('.css')) return;
    return code.replace(/,\s*url\([^)]+\.woff\)\s*format\(["']woff["']\)|,\s*url\([^)]+\.ttf\)\s*format\(["']truetype["']\)/g, '');
  },
};

// Mermaid's optional ELK layout is 1.4 MB of EPL-2.0 code, loaded only by a diagram that asks for it. Such a diagram
// is laid out by Mermaid's default dagre layout instead, which exports the same `render`.
const dagreForElk = {
  name: 'dagre-for-elk',
  enforce: 'pre' as const,
  resolveId(source: string, importer?: string) {
    if (!importer?.includes('/node_modules/mermaid/') || !/^\.\/elk-[A-Z0-9]+\.mjs$/.test(source)) return;
    const dagre = readdirSync(path.dirname(importer)).find((name) => /^dagre-[A-Z0-9]+\.mjs$/.test(name));
    if (!dagre) throw new Error('Mermaid no longer has a dagre layout chunk next to its ELK chunk; update vite.config.ts');
    return path.join(path.dirname(importer), dagre);
  },
};

export default defineConfig({
  plugins: [woff2Only, dagreForElk, svelte()],
  build: {
    outDir: '../guided_learning/web_dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
  },
  server: {
    proxy: {
      // The host only accepts its own loopback origin, so the dev proxy drops the browser Origin.
      '/api': {
        target: host,
        changeOrigin: true,
        configure: (proxy) => proxy.on('proxyReq', (request) => request.removeHeader('origin')),
      },
    },
  },
});
