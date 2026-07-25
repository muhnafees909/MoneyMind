import { expect, type Page } from '@playwright/test';

/**
 * Reusable UI actions built entirely on accessibility-tree selectors
 * (getByRole / getByLabel / getByPlaceholder), so they survive styling churn.
 */

export interface ManualTransaction {
  amount: number | string;
  description: string;
  /** Category display name, e.g. "Food & Drink" (expense only). */
  category: string;
}

/** Open the Add Transaction modal, fill it, and save. Assumes an expense
 *  (the form's default type) so a category is required. */
export async function addManualTransaction(page: Page, tx: ManualTransaction): Promise<void> {
  await page.getByRole('button', { name: 'Add transaction' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Add Transaction' })).toBeVisible();

  await dialog.getByPlaceholder('0.00').fill(String(tx.amount));

  // Custom category dropdown: open the trigger, then pick the option by text.
  await dialog.getByRole('button', { name: 'Select a category' }).click();
  await dialog.getByText(tx.category, { exact: true }).click();

  await dialog.getByPlaceholder('Enter transaction description').fill(tx.description);
  await dialog.getByRole('button', { name: 'Save Transaction' }).click();

  await expect(dialog).toBeHidden();
}
