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
    MatNativeDateModule
  ],
  templateUrl: './transaction-form.html',
  styleUrl: './transaction-form.scss',
})
export class TransactionForm {
  transaction: any = {
    amount: null,
    description: '',
    category: '',
    transaction_type: 'expense',
    transaction_date: new Date(),
    transaction_notes: ''
  };

  dateInput: string = '';
  showCategoryDropdown: boolean = false;
  showTypeDropdown: boolean = false;

  categories = [
    'groceries',
    'dining',
    'transportation',
    'utilities',
    'entertainment',
    'shopping',
    'healthcare',
    'travel',
    'education',
    'other'
  ];

  constructor(
    public dialogRef: MatDialogRef<TransactionForm>,
    @Inject(MAT_DIALOG_DATA) public data: any
  ) {
    if (data && data.transaction) {
      this.transaction = { ...data.transaction };
      if (typeof this.transaction.transaction_date === 'string') {
        this.transaction.transaction_date = new Date(this.transaction.transaction_date);
      }
    }

    this.dateInput = this.formatDateForInput(this.transaction.transaction_date);
  }

  formatDateForInput(date: any): string {
    if (!date) return '';
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
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

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.dateInput) {
      this.transaction.transaction_date = new Date(this.dateInput);
    }

    const formattedTransaction = {
      ...this.transaction,
      transaction_date: this.transaction.transaction_date.toISOString().split('T')[0],
      category: this.transaction.transaction_type === 'income' ? '' : this.transaction.category
    };
    this.dialogRef.close(formattedTransaction);
  }
}
