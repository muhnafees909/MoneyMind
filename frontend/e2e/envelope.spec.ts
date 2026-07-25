import { test, expect } from './fixtures';

test.describe('Envelopes / goals', () => {
  test('creates a goal and allocates money into it', async ({ page, authedUser }) => {
    void authedUser;

    await page.goto('/envelopes');
    await expect(page.getByRole('heading', { name: 'Goals & Envelopes', level: 1 })).toBeVisible();

    // --- Create a target-only goal (no linked bank account needed) ---
    const goalName = `E2E Goal ${Date.now()}`;
    await page.getByRole('button', { name: 'New goal' }).click();
    await page.getByRole('textbox', { name: 'Name' }).fill(goalName);
    await page.getByRole('spinbutton', { name: 'Target amount' }).fill('1000');
    await page.getByRole('button', { name: 'Create goal' }).click();

    // The goal card renders. Scope later actions/assertions to it.
    const goalCard = page.getByRole('listitem').filter({ hasText: goalName });
    await expect(goalCard).toBeVisible();

    // --- Allocate $50 toward the goal ---
    await goalCard.getByRole('button', { name: 'Add money' }).click();
    await goalCard.getByRole('spinbutton', { name: 'Amount' }).fill('50');
    await goalCard.getByRole('button', { name: 'Add', exact: true }).click();

    // Saved amount updates to $50.00 of $1,000.00.
    await expect(goalCard.getByText('$50.00')).toBeVisible();
  });
});
