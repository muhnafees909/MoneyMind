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
      // Convert date string to Date object if needed
      if (typeof this.transaction.transaction_date === 'string') {
        this.transaction.transaction_date = new Date(this.transaction.transaction_date);
      }
    }
  }
  
  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    // Format date as YYYY-MM-DD
    const formattedTransaction = {
      ...this.transaction,
      transaction_date: this.transaction.transaction_date.toISOString().split('T')[0]
    };
    this.dialogRef.close(formattedTransaction);
  }
}
