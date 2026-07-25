import { test, expect, registerViaApi, loginViaUi, uniqueEmail, TEST_PASSWORD } from './fixtures';

test.describe('Login', () => {
  test('signs in with valid credentials and lands on the dashboard', async ({ page, request }) => {
    const email = uniqueEmail('login');
    await registerViaApi(request, email);

    await loginViaUi(page, email);

    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('shows an error and stays on the login page for a wrong password', async ({
    page,
    request,
  }) => {
    const email = uniqueEmail('login');
    await registerViaApi(request, email);

    await page.goto('/login');
    await page.getByRole('textbox', { name: 'Email' }).fill(email);
    await page.getByPlaceholder('Enter your password').fill(`${TEST_PASSWORD}-wrong`);
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });
});
