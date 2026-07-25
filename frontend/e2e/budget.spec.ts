import { test, expect } from './fixtures';

test.describe('Budgets', () => {
  test('creates a monthly budget for a category', async ({ page, authedUser }) => {
    void authedUser;

    await page.goto('/budgets');
    await expect(page.getByRole('heading', { name: 'Budgets', level: 1 })).toBeVisible();

    await page.getByRole('button', { name: 'New budget' }).click();
    await page.getByRole('combobox', { name: 'Category' }).selectOption({ label: 'Food & Drink' });
    await page.getByRole('spinbutton', { name: 'Monthly limit' }).fill('500');
    await page.getByRole('button', { name: 'Create budget' }).click();

    // The category row renders with the configured limit.
    const budgetRow = page.getByRole('listitem').filter({ hasText: 'Food & Drink' });
    await expect(budgetRow).toBeVisible();
    await expect(budgetRow.getByText('$500.00')).toBeVisible();
  });
});
