import { Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { animate, stagger } from 'motion';
import {
  LucideBan,
  LucideCheck,
  LucideChevronDown,
  LucidePlus,
  LucideRefreshCw,
  LucideRepeat,
  LucideSearch,
  LucideTriangleAlert,
  LucideX
} from '@lucide/angular';
import { RecurringService, RecurringExpense } from '../../services/recurring.service';
import { CategoryService, CategoryInfo } from '../../services/category.service';
import { ModalService } from '../../services/modal.service';
import { TransactionService } from '../../services/transactionService';
import { CountUpDirective } from '../../shared/count-up.directive';
import { CATEGORY_COLORS, OTHER_COLOR } from '../../shared/category-colors';

type Cadence = 'weekly' | 'biweekly' | 'monthly' | 'annual';

@Component({
  selector: 'app-recurring',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CountUpDirective,
    LucideBan,
    LucideCheck,
    LucideChevronDown,
    LucidePlus,
    LucideRefreshCw,
    LucideRepeat,
    LucideSearch,
    LucideTriangleAlert,
    LucideX
  ],
  templateUrl: './recurring.html',
  styleUrl: './recurring.scss'
})
export class RecurringComponent implements OnInit {
  reviewQueue: RecurringExpense[] = [];
  confirmed: RecurringExpense[] = [];
  loading = true;
  detecting = false;
  totalMonthly = 0;

  initialLoading = true;
  revealed = false;
  preAnim = true;
  private entranceDone = false;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  Math = Math;

  categories: CategoryInfo[] = [];
  // per-series category override while confirming
  reviewCategory: { [id: number]: string } = {};
  expandedSeries: number | null = null;

  // ----- Add-recurring form state -----
  showAddForm = false;
  addMode: 'history' | 'manual' = 'history';
  creating = false;

  // History picker
  allTransactions: any[] = [];
  loadingTransactions = false;
  txnSearch = '';
  selectedTxnIds: number[] = [];

  // Confirm fields (prefilled from selection, editable)
  form = {
    name: '',
    category: '',
    expected_amount: null as number | null,
    cadence: 'monthly' as Cadence
  };

  // Free-text fallback
  manualEntry = {
    category: '',
    expected_amount: null as number | null,
    cadence: 'monthly' as Cadence,
    description: ''
  };

  constructor(
    private recurringService: RecurringService,
    public categoryService: CategoryService,
    private modalService: ModalService,
    private transactionService: TransactionService,
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {
    this.categories = this.categoryService.getAllCategories();
    // Refresh so custom categories appear even if this loads before the cache warms
    this.categoryService.refresh().subscribe({
      next: () => (this.categories = this.categoryService.getAllCategories()),
      error: () => {}
    });
    if (this.reducedMotion) {
      this.preAnim = false;
    }
  }

  ngOnInit() {
    this.detectAndLoad();
  }

  detectAndLoad() {
    this.detecting = true;
    this.recurringService.detect().subscribe({
      next: () => {
        this.detecting = false;
        this.loadAll();
      },
      error: () => {
        this.detecting = false;
        this.loadAll(); // detection failing shouldn't hide existing data
      }
    });
  }

  loadAll() {
    this.loading = true;
    this.recurringService.getRecurring('review').subscribe({
      next: (data) => {
        this.reviewQueue = data;
        for (const series of data) {
          this.reviewCategory[series.id] = series.category || '';
        }
      },
      error: (error) => console.error('Error loading review queue:', error)
    });
    this.recurringService.getRecurring('confirmed').subscribe({
      next: (data) => {
        this.confirmed = data;
        this.totalMonthly = data.reduce((sum, s) => sum + s.monthly_equivalent, 0);
        this.loading = false;
        this.finishFirstLoad();
      },
      error: (error) => {
        console.error('Error loading recurring expenses:', error);
        this.loading = false;
        this.finishFirstLoad();
      }
    });
  }

  private finishFirstLoad() {
    if (!this.initialLoading) {
      return;
    }
    this.initialLoading = false;
    setTimeout(() => {
      this.revealed = true;
      this.runEntrance();
    }, 40);
  }

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
        const rows = Array.from(this.host.nativeElement.querySelectorAll('.tx-table tbody tr'));
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

  categoryColor(category: string | null): string {
    return (
      this.categoryService.getCategoryColor(category) ||
      CATEGORY_COLORS[(category || '').toUpperCase()] ||
      OTHER_COLOR
    );
  }

  yearlyTotal(): number {
    return this.totalMonthly * 12;
  }

  confirm(series: RecurringExpense) {
    const category = this.reviewCategory[series.id] || undefined;
    this.recurringService.confirm(series.id, category).subscribe({
      next: () => this.loadAll(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to confirm')
    });
  }

  dismiss(series: RecurringExpense) {
    this.recurringService.dismiss(series.id).subscribe({
      next: () => this.loadAll(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to dismiss')
    });
  }

  async cancelSeries(series: RecurringExpense) {
    const confirmed = await this.modalService.showConfirm(
      `Mark "${series.merchant_name}" as cancelled? It will stop counting toward your recurring total.`,
      'Cancel Subscription', 'Yes, cancelled', 'Keep');
    if (!confirmed) return;
    this.recurringService.update(series.id, { status: 'cancelled_by_user' } as any).subscribe({
      next: () => this.loadAll(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to update')
    });
  }

  updateCategory(series: RecurringExpense, category: string) {
    this.recurringService.update(series.id, { category } as any).subscribe({
      next: () => this.loadAll(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to update category')
    });
  }

  toggleExpand(series: RecurringExpense) {
    this.expandedSeries = this.expandedSeries === series.id ? null : series.id;
  }

  cadenceLabel(cadence: string): string {
    return { weekly: 'Weekly', biweekly: 'Every 2 weeks', monthly: 'Monthly', annual: 'Yearly' }[cadence] || cadence;
  }

  // ----- Add-recurring form -----

  openAddForm() {
    this.showAddForm = true;
    this.addMode = 'history';
    this.resetForm();
    this.loadTransactionsForPicker();
  }

  closeAddForm() {
    this.showAddForm = false;
    this.resetForm();
  }

  resetForm() {
    this.selectedTxnIds = [];
    this.txnSearch = '';
    this.form = { name: '', category: '', expected_amount: null, cadence: 'monthly' };
    this.manualEntry = { category: '', expected_amount: null, cadence: 'monthly', description: '' };
  }

  loadTransactionsForPicker() {
    this.loadingTransactions = true;
    this.transactionService.getTransactions().subscribe({
      next: (data: any[]) => {
        // Only expenses can back a recurring bill; newest first
        this.allTransactions = (data || [])
          .filter((t) => t.transaction_type === 'expense')
          .sort((a, b) => (a.transaction_date < b.transaction_date ? 1 : -1));
        this.loadingTransactions = false;
      },
      error: () => {
        this.loadingTransactions = false;
        this.modalService.showError('Could not load your transactions');
      }
    });
  }

  filteredTransactions(): any[] {
    const q = this.txnSearch.trim().toLowerCase();
    const list = q
      ? this.allTransactions.filter(
          (t) =>
            (t.description || '').toLowerCase().includes(q) ||
            String(t.amount).includes(q)
        )
      : this.allTransactions;
    return list.slice(0, 50); // keep the list manageable
  }

  isSelected(txn: any): boolean {
    return this.selectedTxnIds.includes(txn.id);
  }

  toggleTxn(txn: any) {
    if (this.isSelected(txn)) {
      this.selectedTxnIds = this.selectedTxnIds.filter((id) => id !== txn.id);
    } else {
      if (this.selectedTxnIds.length >= 3) {
        this.modalService.showError('Pick at most 3 payments', 'Selection limit');
        return;
      }
      this.selectedTxnIds = [...this.selectedTxnIds, txn.id];
    }
    this.prefillFromSelection();
  }

  private selectedTransactions(): any[] {
    return this.allTransactions.filter((t) => this.selectedTxnIds.includes(t.id));
  }

  /** Recompute the confirm-field defaults from the current selection. */
  private prefillFromSelection() {
    const picks = this.selectedTransactions();
    if (picks.length === 0) return;

    const latest = [...picks].sort((a, b) => (a.transaction_date < b.transaction_date ? 1 : -1))[0];
    this.form.name = latest.merchant_name || latest.description || '';

    const sum = picks.reduce((s, t) => s + Number(t.amount || 0), 0);
    this.form.expected_amount = Math.round((sum / picks.length) * 100) / 100;

    // Most common category among the picks
    const counts: { [c: string]: number } = {};
    for (const t of picks) {
      if (t.category) counts[t.category] = (counts[t.category] || 0) + 1;
    }
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    if (top) this.form.category = top[0];

    const inferred = this.detectedCadence();
    if (inferred) this.form.cadence = inferred;
  }

  /** Client-side cadence hint from the selected dates (mirrors the server bands). */
  detectedCadence(): Cadence | null {
    const dates = this.selectedTransactions()
      .map((t) => new Date(t.transaction_date).getTime())
      .sort((a, b) => a - b);
    if (dates.length < 2) return null;

    const gaps: number[] = [];
    for (let i = 1; i < dates.length; i++) {
      gaps.push((dates[i] - dates[i - 1]) / (1000 * 60 * 60 * 24));
    }
    const avg = gaps.reduce((s, g) => s + g, 0) / gaps.length;
    if (avg >= 5 && avg <= 9) return 'weekly';
    if (avg >= 11 && avg <= 18) return 'biweekly';
    if (avg >= 24 && avg <= 36) return 'monthly';
    if (avg >= 330 && avg <= 400) return 'annual';
    return null;
  }

  submitFromHistory() {
    if (this.selectedTxnIds.length === 0) {
      this.modalService.showError('Select 1–3 past payments first', 'Validation Error');
      return;
    }
    if (!this.form.category || !this.form.expected_amount) {
      this.modalService.showError('Category and amount are required', 'Validation Error');
      return;
    }

    this.creating = true;
    this.recurringService
      .createFromTransactions({
        transaction_ids: this.selectedTxnIds,
        category: this.form.category,
        name: this.form.name || undefined,
        cadence: this.form.cadence,
        expected_amount: this.form.expected_amount
      })
      .subscribe({
        next: () => {
          this.creating = false;
          this.closeAddForm();
          this.modalService.showSuccess('Now tracking this recurring bill', 'Success');
          this.loadAll();
        },
        error: (error) => {
          this.creating = false;
          this.modalService.showError(error?.error?.error || 'Failed to create recurring expense');
        }
      });
  }

  submitManual() {
    if (!this.manualEntry.category || !this.manualEntry.expected_amount) {
      this.modalService.showError('Category and amount are required', 'Validation Error');
      return;
    }

    this.creating = true;
    this.recurringService
      .createManual({
        category: this.manualEntry.category,
        expected_amount: this.manualEntry.expected_amount,
        cadence: this.manualEntry.cadence,
        description: this.manualEntry.description || undefined
      })
      .subscribe({
        next: () => {
          this.creating = false;
          this.closeAddForm();
          this.modalService.showSuccess('Recurring expense created', 'Success');
          this.loadAll();
        },
        error: (error) => {
          this.creating = false;
          this.modalService.showError(error?.error?.error || 'Failed to create recurring expense');
        }
      });
  }
}
