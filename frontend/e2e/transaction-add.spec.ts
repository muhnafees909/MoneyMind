import { test, expect } from './fixtures';
import { addManualTransaction } from './actions';

test.describe('Add manual transaction', () => {
  test('creates a manual expense that appears in the ledger', async ({ page, authedUser }) => {
    void authedUser; // fixture signs us in

    await page.goto('/transactions');
    await expect(page.getByRole('heading', { name: 'Transactions', level: 1 })).toBeVisible();

    const description = `Coffee ${Date.now()}`;
    await addManualTransaction(page, {
      amount: 4.5,
      description,
      category: 'Food & Drink',
    });

    // The new row shows up in the history table.
    await expect(page.getByRole('cell', { name: description })).toBeVisible();
  });
});
