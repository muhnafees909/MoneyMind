import { defineConfig, devices } from '@playwright/test';

/**
 * MoneyMind end-to-end regression suite.
 *
 * Requires BOTH servers running against a real Postgres DB:
 *   - Backend  : http://localhost:5000  (cd backend && python app.py)
 *   - Frontend : http://localhost:4200  (auto-started below via `npm start`)
 *
 * Each test provisions its own fresh user (see e2e/fixtures.ts), so specs are
 * independent and safe to run in parallel.
 */
const FRONTEND_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:4200';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env['CI'],
  retries: process.env['CI'] ? 2 : 0,
  workers: process.env['CI'] ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: FRONTEND_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Starts the Angular dev server if it isn't already up. The backend must be
  // started separately (it needs the Python venv + Postgres).
  webServer: {
    command: 'npm start',
    url: FRONTEND_URL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
