import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { LucideOctagonAlert, LucideX } from '@lucide/angular';
import { CategoryService, CategoryInfo } from '../../services/category.service';

@Component({
  selector: 'app-transaction-form',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    LucideOctagonAlert,
    LucideX
  ],
  templateUrl: './transaction-form.html',
  styleUrl: './transaction-form.scss',
})
export class TransactionForm {
  // Mirrors the backend cap (routes/transactions.py MAX_AMOUNT) and stays
  // well within the NUMERIC(10,2) column so a valid amount never overflows.
  readonly maxAmount = 10_000_000;

  transaction: any = {
    amount: null,
    description: '',
    category: '',
    transaction_type: 'expense',
    transaction_date: new Date(),
    transaction_notes: ''
  };

  showCategoryDropdown: boolean = false;
  showTypeDropdown: boolean = false;

  categories: CategoryInfo[] = [];

  // Money-in categories — they describe income, so they don't belong in the
  // expense category picker (the only place the picker is shown).
  private readonly incomeOnlyCategories = ['INCOME', 'TRANSFER_IN'];

  constructor(
    public dialogRef: MatDialogRef<TransactionForm>,
    @Inject(MAT_DIALOG_DATA) public data: any,
    private categoryService: CategoryService
  ) {
    this.categories = this.categoryService.getAllCategories();
    if (data && data.transaction) {
      this.transaction = { ...data.transaction };
      if (typeof this.transaction.transaction_date === 'string') {
        this.transaction.transaction_date = new Date(this.transaction.transaction_date);
      }
    }
  }

  /** Categories offered in the expense picker — excludes money-in categories. */
  get selectableCategories(): CategoryInfo[] {
    return this.categories.filter((c) => !this.incomeOnlyCategories.includes(c.value));
  }

  toggleCategoryDropdown(): void {
    this.showCategoryDropdown = !this.showCategoryDropdown;
    this.showTypeDropdown = false;
  }

  toggleTypeDropdown(): void {
    this.showTypeDropdown = !this.showTypeDropdown;
    this.showCategoryDropdown = false;
  }

  selectCategory(category: string): void {
    this.transaction.category = category;
    this.showCategoryDropdown = false;
  }

  selectType(type: string): void {
    this.transaction.transaction_type = type;
    this.showTypeDropdown = false;

    if (type === 'income') {
      this.transaction.category = '';
    }
  }

  /**
   * Inline amount validation message, or null when the amount is acceptable.
   * Drives both the inline error and the disabled state of Save.
   */
  get amountError(): string | null {
    const raw = this.transaction.amount;
    if (raw === null || raw === undefined || raw === '') {
      return null; // empty is handled by `required` / the disabled Save button
    }
    const amount = Number(raw);
    if (isNaN(amount)) {
      return 'Enter a valid amount.';
    }
    if (amount <= 0) {
      return 'Amount must be greater than zero.';
    }
    if (amount > this.maxAmount) {
      return `Amount must be at most $${this.maxAmount.toLocaleString('en-US')}.`;
    }
    return null;
  }

  get canSave(): boolean {
    return (
      !!this.transaction.amount &&
      !!this.transaction.description &&
      this.amountError === null &&
      !(this.transaction.transaction_type === 'expense' && !this.transaction.category)
    );
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    // Guard against submission even if the button's disabled state is bypassed
    if (!this.canSave) {
      return;
    }
    const formattedTransaction = {
      ...this.transaction,
      transaction_date: this.transaction.transaction_date instanceof Date
        ? this.transaction.transaction_date.toISOString().split('T')[0]
        : this.transaction.transaction_date,
      category: this.transaction.transaction_type === 'income' ? '' : this.transaction.category
    };
    this.dialogRef.close(formattedTransaction);
  }

  getCategoryDisplayName(value: string): string {
    return this.categoryService.getCategoryDisplayName(value);
  }
}
