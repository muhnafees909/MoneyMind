import { Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { animate, stagger } from 'motion';
import {
  LucideCheck,
  LucideChevronLeft,
  LucideChevronRight,
  LucideCircleCheck,
  LucideOctagonAlert,
  LucidePencil,
  LucidePlus,
  LucideRepeat,
  LucideTrash2,
  LucideTriangleAlert,
  LucideWallet,
  LucideX
} from '@lucide/angular';
import { BudgetService } from '../../services/budget.service';
import { CategoryService, CategoryInfo } from '../../services/category.service';
import { ModalService } from '../../services/modal.service';
import { RecurringService } from '../../services/recurring.service';
import { CountUpDirective } from '../../shared/count-up.directive';
import { CATEGORY_COLORS, OTHER_COLOR } from '../../shared/category-colors';

interface BudgetRow {
  budget_id: number;
  category: string;
  budgeted: number;
  spent: number;
  remaining: number;
  percentage: number;
  state: 'ok' | 'warn' | 'over';
}

@Component({
  selector: 'app-budget-manager',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CountUpDirective,
    LucideCheck,
    LucideChevronLeft,
    LucideChevronRight,
    LucideCircleCheck,
    LucideOctagonAlert,
    LucidePencil,
    LucidePlus,
    LucideRepeat,
    LucideTrash2,
    LucideTriangleAlert,
    LucideWallet,
    LucideX
  ],
  templateUrl: './budget-manager.html',
  styleUrl: './budget-manager.scss'
})
export class BudgetManager implements OnInit {
  budgetRows: BudgetRow[] = [];
  totals = { budgeted: 0, spent: 0, left: 0, overCount: 0 };

  // Month being viewed (budgets are recurring; spending is per-month)
  viewMonth: number;
  viewYear: number;
  private readonly now = new Date();

  // Create / edit state
  showAddPanel = false;
  newBudget = { category: '', amount: null as number | null };
  editingId: number | null = null;
  editingAmount: number | null = null;

  categories: CategoryInfo[] = [];
  recurringByCategory: { [category: string]: { monthly_total: number; count: number } } = {};

  initialLoading = true;
  revealed = false;
  preAnim = true;
  private entranceDone = false;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  Math = Math;

  constructor(
    private budgetService: BudgetService,
    public categoryService: CategoryService,
    private modalService: ModalService,
    private recurringService: RecurringService,
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {
    this.categories = this.categoryService.getAllCategories();
    // Pull the latest (includes the user's custom categories) in case this is
    // the first screen loaded before the shared cache warmed up.
    this.categoryService.refresh().subscribe({
      next: () => (this.categories = this.categoryService.getAllCategories()),
      error: () => {}
    });
    this.viewMonth = this.now.getMonth() + 1;
    this.viewYear = this.now.getFullYear();
    if (this.reducedMotion) {
      this.preAnim = false;
    }
  }

  ngOnInit() {
    this.loadProgress(true);
    this.loadRecurringSummary();
  }

  loadProgress(first = false) {
    this.budgetService.getBudgetProgress(this.viewMonth, this.viewYear).subscribe({
      next: (data) => {
        this.budgetRows = (data || [])
          .map((p: any) => ({
            budget_id: p.budget_id,
            category: p.category,
            budgeted: p.budgeted,
            spent: p.spent,
            remaining: p.remaining,
            percentage: p.percentage,
            state: (p.percentage >= 100
              ? 'over'
              : p.percentage >= 85
                ? 'warn'
                : 'ok') as BudgetRow['state']
          }))
          .sort((a: BudgetRow, b: BudgetRow) => b.percentage - a.percentage);
        this.totals = {
          budgeted: this.budgetRows.reduce((s, r) => s + r.budgeted, 0),
          spent: this.budgetRows.reduce((s, r) => s + r.spent, 0),
          left: this.budgetRows.reduce((s, r) => s + r.remaining, 0),
          overCount: this.budgetRows.filter((r) => r.state === 'over').length
        };
        if (first) {
          this.initialLoading = false;
          setTimeout(() => {
            this.revealed = true;
            this.runEntrance();
          }, 40);
        }
      },
      error: (error) => {
        console.error('Error loading budget progress:', error);
        if (first) {
          this.initialLoading = false;
        }
      }
    });
  }

  loadRecurringSummary() {
    this.recurringService.getSummary().subscribe({
      next: (summary) => {
        this.recurringByCategory = {};
        for (const entry of summary.categories) {
          this.recurringByCategory[entry.category] = {
            monthly_total: entry.monthly_total,
            count: entry.count
          };
        }
      },
      error: (error) => console.error('Error loading recurring summary:', error)
    });
  }

  recurringFor(category: string) {
    return this.recurringByCategory[category] || null;
  }

  // ============================================
  // MONTH STEPPER — the screen's interactive moment:
  // stepping re-runs the meters and counts against that month's spending
  // ============================================

  monthLabel(): string {
    const date = new Date(this.viewYear, this.viewMonth - 1);
    const sameYear = this.viewYear === this.now.getFullYear();
    return date.toLocaleDateString('en-US', {
      month: 'long',
      ...(sameYear ? {} : { year: 'numeric' })
    });
  }

  isCurrentMonth(): boolean {
    return this.viewMonth === this.now.getMonth() + 1 && this.viewYear === this.now.getFullYear();
  }

  prevMonth() {
    this.viewMonth--;
    if (this.viewMonth < 1) {
      this.viewMonth = 12;
      this.viewYear--;
    }
    this.loadProgress();
  }

  nextMonth() {
    if (this.isCurrentMonth()) {
      return;
    }
    this.viewMonth++;
    if (this.viewMonth > 12) {
      this.viewMonth = 1;
      this.viewYear++;
    }
    this.loadProgress();
  }

  // ============================================
  // CREATE / EDIT / DELETE
  // ============================================

  toggleAddPanel() {
    this.showAddPanel = !this.showAddPanel;
    if (!this.showAddPanel) {
      this.newBudget = { category: '', amount: null };
    }
  }

  availableCategories(): CategoryInfo[] {
    const used = new Set(this.budgetRows.map((r) => r.category));
    return this.categories.filter((c) => !used.has(c.value) && c.value !== 'INCOME');
  }

  addBudget() {
    if (!this.newBudget.category || !this.newBudget.amount) {
      this.modalService.showError('Pick a category and a monthly limit', 'Missing details');
      return;
    }
    this.budgetService.createBudget(this.newBudget).subscribe({
      next: () => {
        this.newBudget = { category: '', amount: null };
        this.showAddPanel = false;
        this.loadProgress();
      },
      error: (error) => {
        console.error('Error creating budget:', error);
        this.modalService.showError(error.error?.error || 'Failed to create budget');
      }
    });
  }

  startEdit(row: BudgetRow) {
    this.editingId = row.budget_id;
    this.editingAmount = row.budgeted;
  }

  cancelEdit() {
    this.editingId = null;
    this.editingAmount = null;
  }

  saveEdit() {
    if (!this.editingAmount || this.editingAmount <= 0) {
      this.modalService.showError('Enter a limit above zero', 'Invalid amount');
      return;
    }
    this.budgetService.updateBudget(this.editingId!, { amount: this.editingAmount }).subscribe({
      next: () => {
        this.cancelEdit();
        this.loadProgress();
      },
      error: (error) => {
        console.error('Error updating budget:', error);
        this.modalService.showError('Failed to update budget');
      }
    });
  }

  async deleteBudget(id: number) {
    const confirmed = await this.modalService.showConfirm(
      'Delete this budget? It repeats every month, so it will stop being tracked.',
      'Confirm Delete',
      'Delete',
      'Cancel'
    );
    if (confirmed) {
      this.budgetService.deleteBudget(id).subscribe({
        next: () => this.loadProgress(),
        error: (error) => console.error('Error deleting budget:', error)
      });
    }
  }

  // ============================================
  // HELPERS
  // ============================================

  categoryColor(category: string): string {
    return (
      this.categoryService.getCategoryColor(category) ||
      CATEGORY_COLORS[(category || '').toUpperCase()] ||
      OTHER_COLOR
    );
  }

  stateLabel(row: BudgetRow): string {
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
      });
    });
  }
}
