import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../services/auth.service';
import { TransactionService } from '../../services/transactionService';
import { CategoryService } from '../../services/category.service';
import { ModalService } from '../../services/modal.service';
import { TransactionForm } from '../transaction-form/transaction-form';
import { RouterLink } from '@angular/router';

declare var Plaid: any;

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
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
  monthlySpendingByCategory: any[] = [];
  monthlySpending: any[] = [];
  summary: any = {};
  monthlySummary: any = {
    month_expenses: 0,
    month_income: 0,
    month_net: 0,
    month_count: 0
  };
  transactions: any[] = [];
  displayedColumns: string[] = ['date', 'description', 'category', 'amount', 'type', 'source', 'actions'];
  loading = true;
  plaidHandler: any = null;
  today = new Date();

  // Filter properties
  showFilters = false;
  filteredTransactions: any[] = [];
  availableMonths: { value: string, display: string }[] = [];
  filters = {
    category: '',
    type: '',
    source: '',
    month: '',
    description: '',
    amountFrom: null as number | null,
    amountTo: null as number | null
  };

  // Pagination properties
  rowsPerPage: number = 20;  // Default to 20
  currentPage: number = 0;   // 0-indexed page number
  rowsPerPageOptions: number[] = [20, 50, 100];  // Options for dropdown
  showAll: boolean = false;  // Track if "All" is selected
  showRowsDropdown: boolean = false;  // Dropdown state

  // Expose Math to template
  Math = Math;
    constructor(
      private authService: AuthService,
      private transactionService: TransactionService,
      public categoryService: CategoryService,
      private router: Router,
      private dialog: MatDialog,
      private modalService: ModalService
    ) {}
  
    ngOnInit() {
      this.loadTransactions(); 
      this.loadAnalytics();
    }
  
    loadAnalytics() {
      this.loading = true;

      // All-time summary
      this.transactionService.getSpendingSummary().subscribe({
        next: (data) => {
          this.summary = data;
        },
        error: (error) => console.error('Error loading summary:', error)
      });

      // Monthly summary
      this.transactionService.getSpendingSummaryMonthly().subscribe({
        next: (data) => {
          this.monthlySummary = data;
        },
        error: (error) => console.error('Error loading monthly summary:', error)
      });

      // Monthly category spending
      this.transactionService.getSpendingByCategoryMonthly().subscribe({
        next: (data) => {
          this.monthlySpendingByCategory = data;
        },
        error: (error) => console.error('Error loading monthly categories:', error)
      });

      // Monthly spending by month for year
      this.transactionService.getMonthlySpending().subscribe({
        next: (data) => {
          this.monthlySpending = data;
          console.log('Monthly spending data:', data);
          console.log('Pie slices:', this.getPieSlices());
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
          this.filteredTransactions = data;
          this.extractAvailableMonths();
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
  
    async deleteTransaction(id: number) {
      const confirmed = await this.modalService.showConfirm(
        'Are you sure you want to delete this transaction?',
        'Confirm Delete',
        'Delete',
        'Cancel'
      );

      if (confirmed) {
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
          this.modalService.showError('Failed to initialize bank connection');
        }
      });
    }

    handlePlaidSuccess(public_token: string, metadata: any) { 
      console.log('Exchange public token...');

      this.authService.exchangePublicToken(public_token).subscribe({
        next: (response) => {
          console.log('Token exchange successful!', response);

          // Access token is now stored in database, just call sync without passing it
          this.authService.syncTransactions().subscribe({
            next: (syncResponse) => {
              console.log('Transactions synced!', syncResponse);
              this.modalService.showSuccess(`Successfully synced ${syncResponse.saved_transactions} transactions!`);

              this.loadAnalytics();
              this.loadTransactions();
            },
            error: (error) => {
              console.error('Error syncing transactions:', error);
              this.modalService.showError('Bank connected but failed to sync transactions');
            }
          });

        },
        error: (error) => {
          console.error('Error exchanging token:', error);
          this.modalService.showError('Failed to complete bank connection');
        }
      });
    }

    

  getCategoryColor(category: string): string {
    return this.categoryService.getCategoryColor(category);
  }

  getCategoryPercentage(total: number): number {
    const max = Math.max(...this.spendingByCategory.map((c: any) => c.total));
    return max > 0 ? (total / max) * 100 : 0;
  }

  getMonthPercentage(total: number): number {
    const max = Math.max(...this.monthlySpending.map((m: any) => m.total));
    return max > 0 ? (total / max) * 100 : 0;
  }

  // Filter methods
  toggleFilters(): void {
    this.showFilters = !this.showFilters;
  }

  applyFilters(): void {
    this.filteredTransactions = this.transactions.filter(txn => {
      // Category filter
      if (this.filters.category && txn.category !== this.filters.category) {
        return false;
      }

      // Type filter
      if (this.filters.type && txn.transaction_type !== this.filters.type) {
        return false;
      }

      // Source filter
      if (this.filters.source && txn.source !== this.filters.source) {
        return false;
      }

      // Month filter (YYYY-MM format)
      if (this.filters.month) {
        const txnMonth = this.formatMonth(new Date(txn.transaction_date));
        if (txnMonth !== this.filters.month) {
          return false;
        }
      }

      // Description filter (case-insensitive contains)
      if (this.filters.description) {
        const desc = txn.description.toLowerCase();
        const search = this.filters.description.toLowerCase();
        if (!desc.includes(search)) {
          return false;
        }
      }

      // Amount filter (range)
      const amount = Number(txn.amount);
      if (this.filters.amountFrom !== null && this.filters.amountFrom !== 0) {
        if (amount < Number(this.filters.amountFrom)) {
          return false;
        }
      }
      if (this.filters.amountTo !== null && this.filters.amountTo !== 0) {
        if (amount > Number(this.filters.amountTo)) {
          return false;
        }
      }

      return true;
    });

    // Reset pagination when filters change
    this.currentPage = 0;
  }

  clearFilters(): void {
    this.filters = {
      category: '',
      type: '',
      source: '',
      month: '',
      description: '',
      amountFrom: null,
      amountTo: null
    };
    this.filteredTransactions = this.transactions;

    // Reset pagination
    this.currentPage = 0;
  }

  formatMonth(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
  }

  extractAvailableMonths(): void {
    const monthsSet = new Set<string>();
    this.transactions.forEach(txn => {
      const monthKey = this.formatMonth(new Date(txn.transaction_date));
      monthsSet.add(monthKey);
    });

    this.availableMonths = Array.from(monthsSet)
      .sort()
      .reverse() // Newest first
      .map(monthKey => {
        const [year, month] = monthKey.split('-');
        const date = new Date(Number(year), Number(month) - 1);
        const display = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        return { value: monthKey, display };
      });
  }

  getDisplayTransactions(): any[] {
    return this.hasActiveFilters()
      ? this.filteredTransactions
      : this.transactions;
  }

  hasActiveFilters(): boolean {
    return !!(
      this.filters.category ||
      this.filters.type ||
      this.filters.source ||
      this.filters.month ||
      this.filters.description ||
      this.filters.amountFrom ||
      this.filters.amountTo
    );
  }

  getCurrentMonthName(): string {
    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return monthNames[new Date().getMonth()];
  }

  getPieSlices(): any[] {
    if (!this.monthlySpending || this.monthlySpending.length === 0) {
      return [];
    }

    const total = this.monthlySpending.reduce((sum, m) => sum + m.total, 0);
    if (total === 0) return [];

    // Special case: if only one month, draw a full circle
    if (this.monthlySpending.length === 1) {
      const month = this.monthlySpending[0];
      const radius = 90;
      return [{
        path: `M 0 -${radius} A ${radius} ${radius} 0 1 1 0 ${radius} A ${radius} ${radius} 0 1 1 0 -${radius}`,
        color: this.getMonthColor(month.month),
        label: month.month_name,
        value: month.total
      }];
    }

    let currentAngle = 0;
    const radius = 90;

    return this.monthlySpending.map((month) => {
      const percentage = month.total / total;
      const angle = percentage * 360;
      const largeArcFlag = angle > 180 ? 1 : 0;

      const startAngle = (currentAngle - 90) * (Math.PI / 180);
      const endAngle = (currentAngle + angle - 90) * (Math.PI / 180);

      const x1 = radius * Math.cos(startAngle);
      const y1 = radius * Math.sin(startAngle);
      const x2 = radius * Math.cos(endAngle);
      const y2 = radius * Math.sin(endAngle);

      const path = [
        `M 0 0`,
        `L ${x1} ${y1}`,
        `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
        `Z`
      ].join(' ');

      currentAngle += angle;

      return {
        path,
        color: this.getMonthColor(month.month),
        label: month.month_name,
        value: month.total
      };
    });
  }

  getCategoryPieSlices(): any[] {
    if (!this.monthlySpendingByCategory || this.monthlySpendingByCategory.length === 0) {
      return [];
    }

    const total = this.monthlySpendingByCategory.reduce((sum, c) => sum + c.total, 0);
    if (total === 0) return [];

    // Special case: if only one category, draw a full circle
    if (this.monthlySpendingByCategory.length === 1) {
      const category = this.monthlySpendingByCategory[0];
      const radius = 90;
      return [{
        path: `M 0 -${radius} A ${radius} ${radius} 0 1 1 0 ${radius} A ${radius} ${radius} 0 1 1 0 -${radius}`,
        color: this.getCategoryColor(category.category),
        label: category.display_name,
        value: category.total
      }];
    }

    let currentAngle = 0;
    const radius = 90;

    return this.monthlySpendingByCategory.map((category) => {
      const percentage = category.total / total;
      const angle = percentage * 360;
      const largeArcFlag = angle > 180 ? 1 : 0;

      const startAngle = (currentAngle - 90) * (Math.PI / 180);
      const endAngle = (currentAngle + angle - 90) * (Math.PI / 180);

      const x1 = radius * Math.cos(startAngle);
      const y1 = radius * Math.sin(startAngle);
      const x2 = radius * Math.cos(endAngle);
      const y2 = radius * Math.sin(endAngle);

      const path = [
        `M 0 0`,
        `L ${x1} ${y1}`,
        `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
        `Z`
      ].join(' ');

      currentAngle += angle;

      return {
        path,
        color: this.getCategoryColor(category.category),
        label: category.display_name,
        value: category.total
      };
    });
  }

  getMonthColor(monthNumber: number): string {
    const colors = [
      'rgba(249, 115, 22, 0.6)',   // Orange
      'rgba(168, 85, 247, 0.6)',   // Purple
      'rgba(34, 197, 94, 0.6)',    // Green
      'rgba(59, 130, 246, 0.6)',   // Blue
      'rgba(239, 68, 68, 0.6)',    // Red
      'rgba(251, 191, 36, 0.6)',   // Yellow
      'rgba(236, 72, 153, 0.6)',   // Pink
      'rgba(16, 185, 129, 0.6)',   // Emerald
      'rgba(139, 92, 246, 0.6)',   // Violet
      'rgba(245, 158, 11, 0.6)',   // Amber
      'rgba(20, 184, 166, 0.6)',   // Teal
      'rgba(244, 63, 94, 0.6)'     // Rose
    ];
    return colors[(monthNumber - 1) % colors.length];
  }

  getMonthColorSolid(monthNumber: number): string {
    const colors = [
      '#f97316',   // Orange
      '#a855f7',   // Purple
      '#22c55e',   // Green
      '#3b82f6',   // Blue
      '#ef4444',   // Red
      '#fbbf24',   // Yellow
      '#ec4899',   // Pink
      '#10b981',   // Emerald
      '#8b5cf6',   // Violet
      '#f59e0b',   // Amber
      '#14b8a6',   // Teal
      '#f43f5e'    // Rose
    ];
    return colors[(monthNumber - 1) % colors.length];
  }

  getCategoryColorSolid(category: string): string {
    const solidColors: {[key: string]: string} = {
      'INCOME': '#4ade80',
      'TRANSFER_IN': '#60a5fa',
      'TRANSFER_OUT': '#818cf8',
      'LOAN_PAYMENTS': '#f87171',
      'BANK_FEES': '#ef4444',
      'ENTERTAINMENT': '#c084fc',
      'FOOD_AND_DRINK': '#fb923c',
      'GENERAL_MERCHANDISE': '#f472b6',
      'HOME_IMPROVEMENT': '#a78bfa',
      'MEDICAL': '#2dd4bf',
      'PERSONAL_CARE': '#fca5a5',
      'GENERAL_SERVICES': '#22d3ee',
      'GOVERNMENT_AND_NON_PROFIT': '#94a3b8',
      'TRANSPORTATION': '#fbbf24',
      'TRAVEL': '#34d399',
      'RENT_AND_UTILITIES': '#38bdf8'
    };
    return solidColors[category?.toUpperCase()] || '#6b7280';
  }

  // ============================================
  // PAGINATION METHODS
  // ============================================

  /**
   * Toggle row limit dropdown visibility
   */
  toggleRowsDropdown(): void {
    this.showRowsDropdown = !this.showRowsDropdown;
  }

  /**
   * Select rows per page and close dropdown
   */
  selectRowsPerPage(limit: number | 'all'): void {
    this.setRowsPerPage(limit);
    this.showRowsDropdown = false;
  }

  /**
   * Change the number of rows displayed per page
   */
  setRowsPerPage(limit: number | 'all'): void {
    if (limit === 'all') {
      this.showAll = true;
      this.rowsPerPage = this.getDisplayTransactions().length;
    } else {
      this.showAll = false;
      this.rowsPerPage = limit;
    }
    this.currentPage = 0;  // Reset to first page
  }

  /**
   * Load the next page of transactions
   */
  showMoreTransactions(): void {
    this.currentPage++;
  }

  /**
   * Get paginated transactions for display
   */
  getPaginatedTransactions(): any[] {
    const allTransactions = this.getDisplayTransactions();

    if (this.showAll) {
      return allTransactions;
    }

    const endIndex = (this.currentPage + 1) * this.rowsPerPage;
    return allTransactions.slice(0, endIndex);
  }

  /**
   * Check if there are more transactions to show
   */
  hasMoreTransactions(): boolean {
    if (this.showAll) {
      return false;
    }

    const allTransactions = this.getDisplayTransactions();
    const currentlyShowing = (this.currentPage + 1) * this.rowsPerPage;
    return currentlyShowing < allTransactions.length;
  }

  /**
   * Get the count of remaining transactions
   */
  getRemainingCount(): number {
    const allTransactions = this.getDisplayTransactions();
    const currentlyShowing = (this.currentPage + 1) * this.rowsPerPage;
    return allTransactions.length - currentlyShowing;
  }

  /**
   * Get the current display range text
   */
  getDisplayRangeText(): string {
    const allTransactions = this.getDisplayTransactions();
    const total = allTransactions.length;

    if (this.showAll || total === 0) {
      return '';
    }

    const showing = Math.min((this.currentPage + 1) * this.rowsPerPage, total);
    return `Showing 1-${showing} of ${total}`;
  }
}