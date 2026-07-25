import { test as base, expect, type Page, type APIRequestContext } from '@playwright/test';

/**
 * Shared test setup. The `authedUser` fixture provisions a brand-new account
 * (via the backend API) and signs in through the real login UI, leaving the
 * page authenticated on the dashboard. Using a unique user per test keeps
 * specs independent and parallel-safe.
 */

export const BACKEND_URL = process.env['E2E_BACKEND_URL'] ?? 'http://localhost:5000';
export const TEST_PASSWORD = 'Test1234!';

export function uniqueEmail(prefix = 'user'): string {
  return `e2e_${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@moneymind.test`;
}

/** Create an account directly against the API — fast setup for tests that
 *  aren't specifically exercising the registration screen. */
export async function registerViaApi(
  request: APIRequestContext,
  email: string,
  password: string = TEST_PASSWORD,
): Promise<void> {
  const res = await request.post(`${BACKEND_URL}/api/auth/register`, {
    data: { email, password, first_name: 'E2E', last_name: 'Tester' },
  });
  if (!res.ok()) {
    throw new Error(`register failed: ${res.status()} ${await res.text()}`);
  }
}

/** Sign in through the real login screen (accessibility-tree selectors). */
export async function loginViaUi(
  page: Page,
  email: string,
  password: string = TEST_PASSWORD,
): Promise<void> {
  await page.goto('/login');
  await page.getByRole('textbox', { name: 'Email' }).fill(email);
  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

type Fixtures = {
  /** A freshly-registered, signed-in user. Page starts on the dashboard. */
  authedUser: { email: string };
};

export const test = base.extend<Fixtures>({
  authedUser: async ({ page, request }, use) => {
    const email = uniqueEmail();
    await registerViaApi(request, email);
    await loginViaUi(page, email);
    await use({ email });
  },
});

export { expect };
