import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: true,
  reporter: 'list',
  // CI retries a failure once and reports it as flaky rather than failing the run (issue #83).
  retries: process.env.CI ? 1 : 0,
  use: { viewport: { width: 1440, height: 900 }, headless: true },
});
