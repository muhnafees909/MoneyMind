import { test, expect } from './fixtures';
import { addManualTransaction } from './actions';

test.describe('Edit transaction category', () => {
  test('changes a transaction category inline via the category chip', async ({
    page,
    authedUser,
  }) => {
    void authedUser;

    await page.goto('/transactions');

    const description = `Lunch ${Date.now()}`;
    await addManualTransaction(page, {
      amount: 12.0,
      description,
      category: 'Food & Drink',
    });

    // The row's category chip is a button labelled with its current category.
    await expect(page.getByRole('cell', { name: description })).toBeVisible();
    await page.getByRole('button', { name: 'Food & Drink' }).click();

    // Inline editor is a native <select aria-label="Change category">.
    await page
      .getByRole('combobox', { name: 'Change category' })
      .selectOption({ label: 'Transportation' });

    // Chip re-renders with the new category; the old one is gone.
    await expect(page.getByRole('button', { name: 'Transportation' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Food & Drink' })).toHaveCount(0);
  });
});
