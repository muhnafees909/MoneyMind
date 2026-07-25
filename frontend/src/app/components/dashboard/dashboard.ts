import { AfterViewInit, Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { animate, stagger } from 'motion';
import {
  LucideArrowDownRight,
  LucideArrowUpRight,
  LucideChartColumn,
  LucideChartPie,
  LucideCheck,
  LucideChevronDown,
  LucideCircleCheck,
  LucideInbox,
  LucideLandmark,
  LucideLock,
  LucideOctagonAlert,
  LucidePencil,
  LucidePlus,
  LucideReceiptText,
  LucideRepeat,
  LucideSlidersHorizontal,
  LucideTarget,
  LucideTrash2,
  LucideTriangleAlert,
  LucideWallet,
  LucideX
} from '@lucide/angular';
import { AuthService } from '../../services/auth.service';
import { TransactionService } from '../../services/transactionService';
import { CategoryService } from '../../services/category.service';
import { BudgetService } from '../../services/budget.service';
import { GoalService } from '../../services/goal.service';
import { ModalService } from '../../services/modal.service';
import { RecurringService, RecurringExpense } from '../../services/recurring.service';
import { TransactionForm } from '../transaction-form/transaction-form';
import { CountUpDirective } from '../../shared/count-up.directive';
import { CATEGORY_COLORS, OTHER_COLOR } from '../../shared/category-colors';

declare var Plaid: any;

interface DonutSegment {
  key: string;
  label: string;
  value: number;
  share: number; // 0–100
  color: string;
}

interface BudgetRow {
  budget_id: number;
  category: string;
  budgeted: number;
  spent: number;
  remaining: number;
  percentage: number;
  state: 'ok' | 'warn' | 'over';
}

interface GoalRing {
  id: number;
  name: string;
  pct: number;
  current: number;
  target: number;
  complete: boolean;
  dashOffset: number;
}

interface MonthColumn {
  month: number;
  label: string;
  name: string;
  total: number;
  hPct: number;
  isCurrent: boolean;
}

// Category → color map now lives in shared/category-colors.ts (one source
// of truth for every screen; mirrors the --mm-cat-* tokens).

// Categories under this share fold into "Other" so the band and its
// breakdown list stay readable
const DONUT_FOLD_SHARE = 0.04;
const GOAL_RING_RADIUS = 30;
const GOAL_RING_CIRCUMFERENCE = 2 * Math.PI * GOAL_RING_RADIUS;

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    RouterLink,
    CountUpDirective,
    LucideArrowDownRight,
    LucideArrowUpRight,
    LucideChartColumn,
    LucideChartPie,
    LucideCheck,
    LucideChevronDown,
    LucideCircleCheck,
    LucideInbox,
    LucideLandmark,
    LucideLock,
    LucideOctagonAlert,
    LucidePencil,
    LucidePlus,
    LucideReceiptText,
    LucideRepeat,
    LucideSlidersHorizontal,
    LucideTarget,
    LucideTrash2,
    LucideTriangleAlert,
    LucideWallet,
    LucideX
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss'
})
export class Dashboard implements OnInit, AfterViewInit {
  summary: any = {};
  monthlySummary: any = { month_expenses: 0, month_income: 0, month_net: 0, month_count: 0 };
  monthlySpendingByCategory: any[] = [];
  monthlySpending: any[] = [];
  transactions: any[] = [];

  // Derived view models
  donutSegments: DonutSegment[] = [];
  donutTotal = 0;
  budgetRows: BudgetRow[] = [];
  budgetTotal = 0;
  budgetLeft = 0;
  goalRings: GoalRing[] = [];
  monthColumns: MonthColumn[] = [];
  sparkPath = '';
  sparkDot: { x: number; y: number } | null = null;

  // Donut interaction (the one interactive moment)
  focusKey: string | null = null;
  lockedKey: string | null = null;

  // Animation state
  initialLoading = true;
  revealed = false;
  preAnim = true;
  private entranceDone = false;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  plaidHandler: any = null;
  today = new Date();

  // Recurring-pattern suggestions awaiting review (detection runs on every
  // transaction write server-side; the dashboard surfaces the queue)
  reviewCandidates: RecurringExpense[] = [];
  suggestionBusy = false;

  // Filters
  showFilters = false;
  filteredTransactions: any[] = [];
  availableMonths: { value: string; display: string }[] = [];
  filters = {
    category: '',
    type: '',
    source: '',
    month: '',
    description: '',
    amountFrom: null as number | null,
    amountTo: null as number | null
  };

  // Pagination
  rowsPerPage = 20;
  currentPage = 0;
  showAll = false;
  showRowsDropdown = false;

  Math = Math;

  constructor(
    private authService: AuthService,
    private transactionService: TransactionService,
    public categoryService: CategoryService,
    private budgetService: BudgetService,
    private goalService: GoalService,
    private recurringService: RecurringService,
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
    this.loadTransactions();
    this.loadAnalytics();
    this.loadRecurringSuggestions();
  }

  // ============================================
  // RECURRING SUGGESTIONS
  // ============================================

  loadRecurringSuggestions() {
    // Detect first (idempotent, catches patterns predating the write-time
    // hook), then surface whatever is waiting for review
    this.recurringService.detect().subscribe({
      next: () => this.fetchReviewQueue(),
      error: () => this.fetchReviewQueue() // still show any known candidates
    });
  }

  private fetchReviewQueue() {
    this.recurringService.getRecurring('review').subscribe({
      next: (list) => (this.reviewCandidates = list),
      error: () => {} // the banner is a courtesy; never block the dashboard
    });
  }

  confirmSuggestion(candidate: RecurringExpense) {
    if (this.suggestionBusy) {
      return;
    }
    this.suggestionBusy = true;
    this.recurringService.confirm(candidate.id).subscribe({
      next: () => {
        this.suggestionBusy = false;
        this.reviewCandidates = this.reviewCandidates.filter((c) => c.id !== candidate.id);
        this.modalService.showSuccess(
          `Now tracking “${candidate.merchant_name}” as a ${candidate.cadence} recurring expense.`
        );
      },
      error: () => {
        this.suggestionBusy = false;
        this.modalService.showError('Could not save that — try again.');
      }
    });
  }

  dismissSuggestion(candidate: RecurringExpense) {
    if (this.suggestionBusy) {
      return;
    }
    this.suggestionBusy = true;
    this.recurringService.dismiss(candidate.id).subscribe({
      next: () => {
        this.suggestionBusy = false;
        this.reviewCandidates = this.reviewCandidates.filter((c) => c.id !== candidate.id);
      },
      error: () => {
        this.suggestionBusy = false;
      }
    });
  }

  ngAfterViewInit() {
    // Entrance runs once data has landed (see loadAnalytics)
  }

  loadAnalytics(refresh = false) {
    if (!refresh) {
      this.initialLoading = true;
    }
    forkJoin({
      summary: this.transactionService.getSpendingSummary().pipe(catchError(() => of({}))),
      monthlySummary: this.transactionService
        .getSpendingSummaryMonthly()
        .pipe(catchError(() => of(this.monthlySummary))),
      byCategory: this.transactionService
        .getSpendingByCategoryMonthly()
        .pipe(catchError(() => of([]))),
      monthlySpending: this.transactionService.getMonthlySpending().pipe(catchError(() => of([]))),
      budgets: this.budgetService.getBudgetProgress().pipe(catchError(() => of([]))),
      goals: this.goalService.getGoals().pipe(catchError(() => of([])))
    }).subscribe((res) => {
      this.summary = res.summary || {};
      this.monthlySummary = res.monthlySummary || this.monthlySummary;
      this.monthlySpendingByCategory = res.byCategory || [];
      this.monthlySpending = res.monthlySpending || [];
      this.buildDonut();
      this.buildBudgets(res.budgets || []);
      this.buildGoals(res.goals || []);
      this.buildMonthColumns();
      this.buildSparkline();
      this.initialLoading = false;
      setTimeout(() => {
        this.revealed = true;
        this.runEntrance();
      }, 40);
    });
  }

  loadTransactions() {
    this.transactionService.getTransactions().subscribe({
      next: (data) => {
        this.transactions = data;
        this.filteredTransactions = data;
        this.extractAvailableMonths();
        if (this.hasActiveFilters()) {
          this.applyFilters();
        }
      },
      error: (error) => console.error('Error loading transactions:', error)
    });
  }

  // ============================================
  // VIEW-MODEL BUILDERS
  // ============================================

  private buildDonut() {
    const source = [...(this.monthlySpendingByCategory || [])]
      .filter((c) => c.total > 0)
      .sort((a, b) => b.total - a.total);
    const total = source.reduce((sum, c) => sum + c.total, 0);
    this.donutTotal = total;
    this.donutSegments = [];
    this.focusKey = null;
    this.lockedKey = null;
    if (total <= 0) {
      return;
    }

    const major = source.filter((c) => c.total / total >= DONUT_FOLD_SHARE).slice(0, 6);
    const rest = source.filter((c) => !major.includes(c));
    const items = major.map((c) => ({
      key: c.category as string,
      label: c.display_name as string,
      value: c.total as number,
      // Prefer the server-resolved color (custom-aware); fall back to the map
      color: (c.color as string) || CATEGORY_COLORS[(c.category || '').toUpperCase()] || OTHER_COLOR
    }));
    if (rest.length > 0) {
      items.push({
        key: '__other__',
        label: 'Other',
        value: rest.reduce((sum, c) => sum + c.total, 0),
        color: OTHER_COLOR
      });
    }

    this.donutSegments = items.map((item) => ({
      ...item,
      share: (item.value / total) * 100
    }));
  }

  private buildBudgets(progress: any[]) {
    this.budgetRows = (progress || [])
      .map((p) => ({
        budget_id: p.budget_id,
        category: p.category,
        budgeted: p.budgeted,
        spent: p.spent,
        remaining: p.remaining,
        percentage: p.percentage,
        state: (p.percentage >= 100 ? 'over' : p.percentage >= 85 ? 'warn' : 'ok') as BudgetRow['state']
      }))
      .sort((a, b) => b.percentage - a.percentage);
    this.budgetTotal = this.budgetRows.reduce((sum, r) => sum + r.budgeted, 0);
    const spent = this.budgetRows.reduce((sum, r) => sum + r.spent, 0);
    this.budgetLeft = this.budgetTotal - spent;
  }

  private buildGoals(goals: any[]) {
    this.goalRings = (goals || []).slice(0, 3).map((g) => {
      const pct = Math.min(Number(g.progress_percentage) || 0, 100);
      return {
        id: g.id,
        name: g.name,
        pct,
        current: Number(g.current_amount) || 0,
        target: Number(g.target_amount) || 0,
        complete: g.is_completed || pct >= 100,
        dashOffset: GOAL_RING_CIRCUMFERENCE * (1 - pct / 100)
      };
    });
  }

  private buildMonthColumns() {
    const byMonth = new Map<number, any>();
    (this.monthlySpending || []).forEach((m) => byMonth.set(m.month, m));
    const max = Math.max(...(this.monthlySpending || []).map((m) => m.total), 0);
    const labels = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
    const names = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    const current = this.today.getMonth() + 1;
    this.monthColumns = labels.map((label, i) => {
      const total = byMonth.get(i + 1)?.total || 0;
      return {
        month: i + 1,
        label,
        name: names[i],
        total,
        hPct: max > 0 ? (total / max) * 100 : 0,
        isCurrent: i + 1 === current
      };
    });
  }

  private buildSparkline() {
    this.sparkPath = '';
    this.sparkDot = null;
    const points = (this.monthlySpending || []).slice().sort((a, b) => a.month - b.month);
    if (points.length < 2) {
      return;
    }
    const w = 120;
    const h = 30;
    const pad = 3;
    const max = Math.max(...points.map((p) => p.total));
    if (max <= 0) {
      return;
    }
    const coords = points.map((p, i) => ({
      x: pad + (i / (points.length - 1)) * (w - pad * 2),
      y: h - pad - (p.total / max) * (h - pad * 2)
    }));
    this.sparkPath = coords
      .map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(2)} ${c.y.toFixed(2)}`)
      .join(' ');
    this.sparkDot = coords[coords.length - 1];
  }

  // ============================================
  // DONUT INTERACTION
  // ============================================

  activeSegment(): DonutSegment | null {
    const key = this.focusKey ?? this.lockedKey;
    if (!key) {
      return null;
    }
    return this.donutSegments.find((s) => s.key === key) || null;
  }

  setFocus(key: string | null) {
    this.focusKey = key;
  }

  toggleLock(key: string) {
    this.lockedKey = this.lockedKey === key ? null : key;
  }

  isActive(seg: DonutSegment): boolean {
    return (this.focusKey ?? this.lockedKey) === seg.key;
  }

  isDimmed(seg: DonutSegment): boolean {
    const active = this.focusKey ?? this.lockedKey;
    return active !== null && active !== seg.key;
  }

  // ============================================
  // MOTION
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
        // Delta line springs in after the balance has mostly counted up
        const chip = this.host.nativeElement.querySelector('.delta-line');
        if (chip) {
          animate(
            chip,
            { opacity: [0, 1], transform: ['scale(0.85)', 'scale(1.05)', 'scale(1)'] },
            { duration: 0.55, delay: 0.55, ease: [0.22, 1, 0.36, 1] }
          );
        }
        // First screenful of transaction rows cascades in
        const rows = Array.from(
          this.host.nativeElement.querySelectorAll('.tx-table tbody tr')
        ).slice(0, 10);
        if (rows.length > 0) {
          animate(
            rows,
            { opacity: [0, 1], transform: ['translateY(8px)', 'translateY(0px)'] },
            { duration: 0.4, delay: stagger(0.035, { startDelay: 0.4 }), ease: 'easeOut' }
          );
        }
        const completed = this.host.nativeElement.querySelectorAll('.goal-ring.complete .ring-svg');
        if (completed.length > 0) {
          animate(
            completed,
            { transform: ['scale(1)', 'scale(1.07)', 'scale(1)'] },
            { duration: 0.7, delay: 1, ease: 'easeInOut' }
          );
        }
      });
    });
  }

  // ============================================
  // TRANSACTION CRUD + PLAID (unchanged behavior)
  // ============================================

  addTransaction() {
    const dialogRef = this.dialog.open(TransactionForm, {
      width: '500px',
      data: { transaction: null }
    });
    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.transactionService.createTransaction(result).subscribe({
          next: () => {
            this.loadTransactions();
            this.loadAnalytics(true);
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
    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.transactionService.updateTransaction(transaction.id, result).subscribe({
          next: () => {
            this.loadTransactions();
            this.loadAnalytics(true);
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
          this.loadAnalytics(true);
        },
        error: (error) => console.error('Error deleting transaction:', error)
      });
    }
  }

  connectBank() {
    this.authService.createLinkToken().subscribe({
      next: (response) => {
        const linkToken = response.link_token;
        this.plaidHandler = Plaid.create({
          token: linkToken,
          onSuccess: (public_token: string, metadata: any) => {
            this.handlePlaidSuccess(public_token, metadata);
          },
          onExit: (err: any, metadata: any) => {
            if (err) {
              console.error('Plaid Link Exit Error:', err);
            }
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
    this.authService.exchangePublicToken(public_token).subscribe({
      next: () => {
        this.authService.syncTransactions().subscribe({
          next: (syncResponse) => {
            this.modalService.showSuccess(
              `Successfully synced ${syncResponse.saved_transactions} transactions!`
            );
            this.loadAnalytics(true);
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

  // ============================================
  // HELPERS
  // ============================================

  categoryColor(category: string): string {
    // Backend-driven: covers custom categories, falls back to the static map
    return (
      this.categoryService.getCategoryColor(category) ||
      CATEGORY_COLORS[(category || '').toUpperCase()] ||
      OTHER_COLOR
    );
  }

  getCurrentMonthName(): string {
    return this.today.toLocaleDateString('en-US', { month: 'long' });
  }

  goalRingCircumference(): number {
    return GOAL_RING_CIRCUMFERENCE;
  }

  budgetStateLabel(row: BudgetRow): string {
    if (row.state === 'over') {
      return `${this.formatShort(Math.abs(row.remaining))} over`;
    }
    if (row.state === 'warn') {
      return `${this.formatShort(row.remaining)} left`;
    }
    return 'On track';
  }

  private formatShort(value: number): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: value >= 1000 ? 0 : 2
    }).format(value);
  }

  // ============================================
  // FILTERS
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
        const txnMonth = this.formatMonth(new Date(txn.transaction_date));
        if (txnMonth !== this.filters.month) {
          return false;
        }
      }
      if (this.filters.description) {
        const desc = txn.description.toLowerCase();
        if (!desc.includes(this.filters.description.toLowerCase())) {
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

  getDisplayTransactions(): any[] {
    return this.hasActiveFilters() ? this.filteredTransactions : this.transactions;
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
