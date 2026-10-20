import { defineConfig } from 'vite';
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

export default defineConfig({
  plugins: [woff2Only, svelte()],
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
