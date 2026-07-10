import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RecurringService, RecurringExpense } from '../../services/recurring.service';
import { CategoryService, CategoryInfo } from '../../services/category.service';
import { ModalService } from '../../services/modal.service';

@Component({
  selector: 'app-recurring',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './recurring.html',
  styleUrl: './recurring.scss'
})
export class RecurringComponent implements OnInit {
  reviewQueue: RecurringExpense[] = [];
  confirmed: RecurringExpense[] = [];
  loading = true;
  detecting = false;
  totalMonthly = 0;

  categories: CategoryInfo[] = [];
  // per-series category override while confirming
  reviewCategory: { [id: number]: string } = {};
  expandedSeries: number | null = null;

  constructor(
    private recurringService: RecurringService,
    public categoryService: CategoryService,
    private modalService: ModalService
  ) {
    this.categories = this.categoryService.getAllCategories();
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
      },
      error: (error) => {
        console.error('Error loading recurring expenses:', error);
        this.loading = false;
      }
    });
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
}
