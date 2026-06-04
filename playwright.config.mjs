import { defineConfig, devices } from '@playwright/test';

// Offline E2E: the spec starts its own static server (no CDN, no webServer).
// Strict timeouts guarantee the run always terminates.
export default defineConfig({
  testDir: './web/e2e',
  timeout: 30_000,
  globalTimeout: 180_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  expect: { timeout: 10_000 },
  use: { headless: true, navigationTimeout: 15_000, actionTimeout: 10_000 },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
