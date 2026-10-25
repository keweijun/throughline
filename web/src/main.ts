import '@fontsource-variable/source-serif-4/opsz.css';
import '@fontsource-variable/source-serif-4/opsz-italic.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import 'katex/dist/katex.min.css';
import './app.css';
import { mount } from 'svelte';
import App from './App.svelte';
import { copyFormulasAsTex } from './lib/selection';

try {
  const theme = localStorage.getItem('theme');
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
} catch {
  // Storage can be unavailable in private windows; the system theme still applies.
}

document.addEventListener('copy', copyFormulasAsTex);
mount(App,{ target: document.getElementById('app')! });
