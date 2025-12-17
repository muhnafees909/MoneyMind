import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../services/auth.service';
import { TransactionService } from '../../services/transactionService';
import { TransactionForm } from '../transaction-form/transaction-form';
import { RouterLink } from '@angular/router';

declare var Plaid: any;

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    MatToolbarModule,
    MatButtonModule,
    MatCardModule,
    MatDialogModule,
    MatTableModule,
    MatIconModule,
    RouterLink
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss'
})
export class Dashboard implements OnInit {
  spendingByCategory: any[] = [];
  monthlySpending: any[] = [];
  summary: any = {};
  transactions: any[] = [];
  displayedColumns: string[] = ['date', 'description', 'category', 'amount', 'type', 'source', 'actions'];  // Add this line
  loading = true;
  plaidHandler: any = null;
  today = new Date();
    constructor(
      private authService: AuthService,
      private transactionService: TransactionService,
      private router: Router,
      private dialog: MatDialog
    ) {}
  
    ngOnInit() {
      this.loadTransactions(); 
      this.loadAnalytics();
    }
  
    loadAnalytics() {
      this.loading = true;
  
      // Get spending summary
      this.transactionService.getSpendingSummary().subscribe({
        next: (data) => {
          this.summary = data;
        },
        error: (error) => console.error('Error loading summary:', error)
      });
  
      // Get spending by category
      this.transactionService.getSpendingByCategory().subscribe({
        next: (data) => {
          this.spendingByCategory = data;
        },
        error: (error) => console.error('Error loading categories:', error)
      });
  
      // Get monthly spending
      this.transactionService.getMonthlySpending().subscribe({
        next: (data) => {
          this.monthlySpending = data;
          this.loading = false;
        },
        error: (error) => {
          console.error('Error loading monthly:', error);
          this.loading = false;
        }
      });
    }
  
    loadTransactions() {
      this.transactionService.getTransactions().subscribe({
        next: (data) => {
          this.transactions = data;
        },
        error: (error) => console.error('Error loading transactions:', error)
      });
    }
  
    addTransaction() {
      const dialogRef = this.dialog.open(TransactionForm, {
        width: '500px',
        data: { transaction: null }
      });
  
      dialogRef.afterClosed().subscribe(result => {
        if (result) {
          this.transactionService.createTransaction(result).subscribe({
            next: () => {
              this.loadTransactions();
              this.loadAnalytics();
            },
            error: (error) => console.error('Error creating transaction:', error)
          });
        }
      });
    }
  
    editTransaction(transaction: any) {
      const dialogRef = this.dialog.open(TransactionForm, {
        width: '500px',
        data: { transaction: transaction }
      });
  
      dialogRef.afterClosed().subscribe(result => {
        if (result) {
          this.transactionService.updateTransaction(transaction.id, result).subscribe({
            next: () => {
              this.loadTransactions();
              this.loadAnalytics();
            },
            error: (error) => console.error('Error updating transaction:', error)
          });
        }
      });
    }
  
    deleteTransaction(id: number) {
      if (confirm('Are you sure you want to delete this transaction?')) {
        this.transactionService.deleteTransaction(id).subscribe({
          next: () => {
            this.loadTransactions();
            this.loadAnalytics();
          },
          error: (error) => console.error('Error deleting transaction:', error)
        });
      }
    }

    logout() {
      this.authService.logout();
      this.router.navigate(['/login']);
    }

    connectBank() {
      this.authService.createLinkToken().subscribe({
        next: (response) => {
          const linkToken = response.link_token;

          // Initialize Plaid Link
          this.plaidHandler = Plaid.create({
            token: linkToken,
            onSuccess: (public_token: string, metadata: any) => {
              console.log('Plaid Link Success!', metadata)
              this.handlePlaidSuccess(public_token, metadata);
            },
            onExit: (err: any, metadata: any) => {
              if (err) {
                console.error('Plaid Link Exit Error:', err);
              }
              console.log('Plaid Link Exited:', metadata);
            }
          });

          this.plaidHandler.open();
        },

        error: (error) => {
          console.error('Error creating link token:', error);
          alert('Failed to initialize bank connection');
        }
      });
    }

    handlePlaidSuccess(public_token: string, metadata: any) { 
      console.log('Exchange public token...');

      this.authService.exchangePublicToken(public_token).subscribe({
        next: (response) => {
          console.log('Token exchange successful!', response);
          const accessToken = response.access_token;

          this.authService.syncTransactions(accessToken).subscribe({
            next: (syncResponse) => {
              console.log('Transactions synced!', syncResponse);
              alert(`Successfully synced ${syncResponse.saved_transactions} transactions!`);
              
              // Reload analytics to show new transactions
              this.loadAnalytics();
            },
            error: (error) => {
              console.error('Error syncing transactions:', error);
              alert('Bank connected but failed to sync transactions');
            }
          });

        },
        error: (error) => {
          console.error('Error exchanging token:', error);
          alert('Failed to complete bank connection');
        }
      });
    }

    

  getCategoryColor(index: number): string {
    const colors = ['#f97316', '#a855f7', '#22c55e', '#ff6b6b', '#3b82f6', '#eab308', '#ec4899', '#06b6d4'];
    return colors[index % colors.length];
  }

  getCategoryPercentage(total: number): number {
    const max = Math.max(...this.spendingByCategory.map((c: any) => c.total));
    return max > 0 ? (total / max) * 100 : 0;
  }

  getMonthPercentage(total: number): number {
    const max = Math.max(...this.monthlySpending.map((m: any) => m.total));
    return max > 0 ? (total / max) * 100 : 0;
  }
}