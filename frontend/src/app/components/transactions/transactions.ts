import { Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { animate, stagger } from 'motion';
import {
  LucideChevronDown,
  LucideInbox,
  LucideLandmark,
  LucideLock,
  LucidePencil,
  LucidePlus,
  LucideRefreshCw,
  LucideSearch,
  LucideSearchX,
  LucideSlidersHorizontal,
  LucideStickyNote,
  LucideTrash2,
  LucideX
} from '@lucide/angular';
import { AuthService } from '../../services/auth.service';
import { TransactionService } from '../../services/transactionService';
import { CategoryService } from '../../services/category.service';
import { ModalService } from '../../services/modal.service';
import { TransactionForm } from '../transaction-form/transaction-form';
import { CountUpDirective } from '../../shared/count-up.directive';
import { CATEGORY_COLORS, OTHER_COLOR } from '../../shared/category-colors';

// Category → color map now lives in shared/category-colors.ts (one source
// of truth for every screen; mirrors the --mm-cat-* tokens).

@Component({
  selector: 'app-transactions',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    CountUpDirective,
    LucideChevronDown,
    LucideInbox,
    LucideLandmark,
    LucideLock,
    LucidePencil,
    LucidePlus,
    LucideRefreshCw,
    LucideSearch,
    LucideSearchX,
    LucideSlidersHorizontal,
    LucideStickyNote,
    LucideTrash2,
    LucideX
  ],
  templateUrl: './transactions.html',
  styleUrl: './transactions.scss'
})
export class TransactionsComponent implements OnInit {
  transactions: any[] = [];
  filteredTransactions: any[] = [];
  availableMonths: { value: string; display: string }[] = [];

  // The screen's working figure: totals for whatever the table currently shows.
  // Filtering/search recomputes these and the hero counts to the new values.
  stats = { net: 0, income: 0, expenses: 0, count: 0 };

  filters = {
    category: '',
    type: '',
    source: '',
    month: '',
    description: '',
    amountFrom: null as number | null,
    amountTo: null as number | null
  };
  showFilters = false;

  rowsPerPage = 20;
  currentPage = 0;
  showAll = false;
  showRowsDropdown = false;

  // Inline category editing: id of the row whose category select is open
  editingCategoryId: number | null = null;
  savingCategoryId: number | null = null;

  // Inline notes editing: id of the row whose note editor is expanded
  notesRowId: number | null = null;
  notesDraft = '';
  savingNotesId: number | null = null;
  readonly notesMaxLen = 255;

  initialLoading = true;
  revealed = false;
  preAnim = true;
  syncing = false;
  private entranceDone = false;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  Math = Math;

  constructor(
    private authService: AuthService,
    private transactionService: TransactionService,
    public categoryService: CategoryService,
    private dialog: MatDialog,
    private modalService: ModalService,
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {
    if (this.reducedMotion) {
      this.preAnim = false;
    }
  }

  ngOnInit() {
    this.loadTransactions(true);
  }

  loadTransactions(first = false) {
    this.transactionService.getTransactions().subscribe({
      next: (data) => {
        this.transactions = data;
        this.extractAvailableMonths();
        this.applyFilters();
        if (first) {
          this.initialLoading = false;
          setTimeout(() => {
            this.revealed = true;
            this.runEntrance();
          }, 40);
        }
      },
      error: (error) => {
        console.error('Error loading transactions:', error);
        if (first) {
          this.initialLoading = false;
        }
      }
    });
  }

  // ============================================
  // MOTION (same choreography as the dashboard)
  // ============================================

  private runEntrance() {
    if (this.entranceDone) {
      return;
    }
    this.entranceDone = true;
    if (this.reducedMotion) {
      this.preAnim = false;
      return;
    }
    setTimeout(() => {
      const els = this.host.nativeElement.querySelectorAll('[data-animate]');
      this.preAnim = false;
      if (els.length === 0) {
        return;
      }
      this.zone.runOutsideAngular(() => {
        animate(
          els,
          { opacity: [0, 1], transform: ['translateY(10px)', 'translateY(0px)'] },
          { duration: 0.5, delay: stagger(0.06), ease: [0.22, 1, 0.36, 1] }
        );
        const rows = Array.from(
          this.host.nativeElement.querySelectorAll('.tx-table tbody tr')
        ).slice(0, 10);
        if (rows.length > 0) {
          animate(
            rows,
            { opacity: [0, 1], transform: ['translateY(8px)', 'translateY(0px)'] },
            { duration: 0.4, delay: stagger(0.035, { startDelay: 0.35 }), ease: 'easeOut' }
          );
        }
      });
    });
  }

  // ============================================
  // CRUD + SYNC
  // ============================================

  addTransaction() {
    const dialogRef = this.dialog.open(TransactionForm, {
      width: '500px',
      data: { transaction: null }
    });
    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.transactionService.createTransaction(result).subscribe({
          next: () => this.loadTransactions(),
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
    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.transactionService.updateTransaction(transaction.id, result).subscribe({
          next: () => this.loadTransactions(),
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
        next: () => this.loadTransactions(),
        error: (error) => console.error('Error deleting transaction:', error)
      });
    }
  }

  // ============================================
  // INLINE NOTES (any transaction — manual or Plaid-synced)
  // ============================================

  hasNote(txn: any): boolean {
    return !!(txn.transaction_notes && txn.transaction_notes.trim().length > 0);
  }

  toggleNotes(txn: any): void {
    if (this.notesRowId === txn.id) {
      this.cancelNotes();
      return;
    }
    // Opening a note closes any open category editor to avoid two open editors
    this.editingCategoryId = null;
    this.notesRowId = txn.id;
    this.notesDraft = txn.transaction_notes || '';
    setTimeout(() => {
      this.host.nativeElement.querySelector<HTMLTextAreaElement>('.note-input')?.focus();
    });
  }

  cancelNotes(): void {
    this.notesRowId = null;
    this.notesDraft = '';
  }

  saveNotes(txn: any): void {
    const next = this.notesDraft.trim();
    if (next === (txn.transaction_notes || '').trim()) {
      this.cancelNotes(); // nothing changed
      return;
    }
    this.savingNotesId = txn.id;
    this.transactionService.updateNotes(txn.id, next).subscribe({
      next: (updated) => {
        txn.transaction_notes = updated.transaction_notes;
        this.savingNotesId = null;
        this.cancelNotes();
      },
      error: (error) => {
        this.savingNotesId = null;
        this.modalService.showError(error?.error?.error || 'Could not save the note — try again.');
      }
    });
  }

  onNotesKeydown(event: KeyboardEvent, txn: any): void {
    // Ctrl/Cmd+Enter saves; Esc cancels (plain Enter makes a new line)
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.saveNotes(txn);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.cancelNotes();
    }
  }

  // ============================================
  // INLINE CATEGORY EDITING
  // ============================================

  startCategoryEdit(txn: any): void {
    if (this.savingCategoryId !== null) {
      return;
    }
    this.notesRowId = null; // don't leave a note editor open behind the select
    this.editingCategoryId = txn.id;
    // Focus the freshly rendered select so keyboard users land in it
    setTimeout(() => {
      this.host.nativeElement.querySelector<HTMLSelectElement>('.cat-select')?.focus();
    });
  }

  cancelCategoryEdit(): void {
    this.editingCategoryId = null;
  }

  async applyCategoryChange(txn: any, newCategory: string): Promise<void> {
    this.editingCategoryId = null;
    if (!newCategory || newCategory === txn.category) {
      return;
    }

    const previous = txn.category;
    // Optimistic: the row updates immediately, server confirms behind it
    txn.category = newCategory;
    txn.category_source = 'manual';
    this.savingCategoryId = txn.id;

    this.transactionService.updateTransaction(txn.id, { category: newCategory }).subscribe({
      next: () => {
        this.savingCategoryId = null;
        this.offerBulkRecategorize(txn, newCategory);
      },
      error: (error) => {
        console.error('Error updating category:', error);
        txn.category = previous;
        this.savingCategoryId = null;
        this.modalService.showError('Could not update the category — try again.');
      }
    });
  }

  /**
   * Same-merchant follow-up: when other transactions from this merchant sit
   * in a different category (Plaid consistently misfiling a merchant), offer
   * to fix them all in one pass.
   */
  private async offerBulkRecategorize(txn: any, newCategory: string): Promise<void> {
    const siblings = this.transactions.filter(
      (t) => t.id !== txn.id && t.category !== newCategory && this.sameMerchant(t, txn)
    );
    if (siblings.length === 0) {
      return;
    }

    const merchant = txn.merchant_name || txn.description;
    const categoryName = this.categoryService.getCategoryDisplayName(newCategory);
    const confirmed = await this.modalService.showConfirm(
      `${siblings.length} other transaction${siblings.length === 1 ? '' : 's'} from ` +
        `“${merchant}” ${siblings.length === 1 ? 'is' : 'are'} filed differently. ` +
        `Move ${siblings.length === 1 ? 'it' : 'them all'} to ${categoryName} too?`,
      'Apply to the whole merchant?',
      `Move ${siblings.length === 1 ? 'it' : 'all'}`,
      'Just this one'
    );
    if (!confirmed) {
      return;
    }

    this.transactionService
      .bulkRecategorize(siblings.map((t) => t.id), newCategory)
      .subscribe({
        next: () => this.loadTransactions(),
        error: (error) => {
          console.error('Error bulk recategorizing:', error);
          this.modalService.showError('Could not update the other transactions — try again.');
        }
      });
  }

  private sameMerchant(a: any, b: any): boolean {
    if (a.merchant_entity_id && b.merchant_entity_id) {
      return a.merchant_entity_id === b.merchant_entity_id;
    }
    const nameA = (a.merchant_name || a.description || '').trim().toLowerCase();
    const nameB = (b.merchant_name || b.description || '').trim().toLowerCase();
    return nameA !== '' && nameA === nameB;
  }

  syncBank() {
    if (this.syncing) {
      return;
    }
    this.syncing = true;
    this.authService.syncTransactions().subscribe({
      next: (res) => {
        this.syncing = false;
        this.modalService.showSuccess(`Synced ${res.saved_transactions} new transactions`);
        this.loadTransactions();
      },
      error: (error) => {
        this.syncing = false;
        console.error('Error syncing transactions:', error);
        this.modalService.showError('Could not sync — link a bank account from the dashboard first');
      }
    });
  }

  // ============================================
  // FILTERS + STATS
  // ============================================

  toggleFilters(): void {
    this.showFilters = !this.showFilters;
  }

  applyFilters(): void {
    this.filteredTransactions = this.transactions.filter((txn) => {
      if (this.filters.category && txn.category !== this.filters.category) {
        return false;
      }
      if (this.filters.type && txn.transaction_type !== this.filters.type) {
        return false;
      }
      if (this.filters.source && txn.source !== this.filters.source) {
        return false;
      }
      if (this.filters.month) {
        if (this.formatMonth(new Date(txn.transaction_date)) !== this.filters.month) {
          return false;
        }
      }
      if (this.filters.description) {
        if (!txn.description.toLowerCase().includes(this.filters.description.toLowerCase())) {
          return false;
        }
      }
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
    this.currentPage = 0;
    this.updateStats();
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
    this.currentPage = 0;
    this.updateStats();
  }

  private updateStats(): void {
    const txs = this.getDisplayTransactions();
    let income = 0;
    let expenses = 0;
    for (const txn of txs) {
      if (txn.transaction_type === 'income') {
        income += Number(txn.amount);
      } else {
        expenses += Number(txn.amount);
      }
    }
    this.stats = { income, expenses, net: income - expenses, count: txs.length };
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

  scopeLabel(): string {
    return this.hasActiveFilters() ? 'Filtered view' : 'All transactions';
  }

  getDisplayTransactions(): any[] {
    return this.hasActiveFilters() ? this.filteredTransactions : this.transactions;
  }

  formatMonth(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
  }

  extractAvailableMonths(): void {
    const monthsSet = new Set<string>();
    this.transactions.forEach((txn) => {
      monthsSet.add(this.formatMonth(new Date(txn.transaction_date)));
    });
    this.availableMonths = Array.from(monthsSet)
      .sort()
      .reverse()
      .map((monthKey) => {
        const [year, month] = monthKey.split('-');
        const date = new Date(Number(year), Number(month) - 1);
        return {
          value: monthKey,
          display: date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
        };
      });
  }

  categoryColor(category: string): string {
    return CATEGORY_COLORS[(category || '').toUpperCase()] || OTHER_COLOR;
  }

  // ============================================
  // PAGINATION
  // ============================================

  toggleRowsDropdown(): void {
    this.showRowsDropdown = !this.showRowsDropdown;
  }

  selectRowsPerPage(limit: number | 'all'): void {
    if (limit === 'all') {
      this.showAll = true;
      this.rowsPerPage = this.getDisplayTransactions().length;
    } else {
      this.showAll = false;
      this.rowsPerPage = limit;
    }
    this.currentPage = 0;
    this.showRowsDropdown = false;
  }

  showMoreTransactions(): void {
    this.currentPage++;
  }

  getPaginatedTransactions(): any[] {
    const all = this.getDisplayTransactions();
    if (this.showAll) {
      return all;
    }
    return all.slice(0, (this.currentPage + 1) * this.rowsPerPage);
  }

  hasMoreTransactions(): boolean {
    if (this.showAll) {
      return false;
    }
    return (this.currentPage + 1) * this.rowsPerPage < this.getDisplayTransactions().length;
  }

  getRemainingCount(): number {
    return this.getDisplayTransactions().length - (this.currentPage + 1) * this.rowsPerPage;
  }

  getDisplayRangeText(): string {
    const total = this.getDisplayTransactions().length;
    if (this.showAll || total === 0) {
      return '';
    }
    const showing = Math.min((this.currentPage + 1) * this.rowsPerPage, total);
    return `Showing 1–${showing} of ${total}`;
  }
}
