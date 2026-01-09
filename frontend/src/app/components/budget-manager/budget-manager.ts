import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { BudgetService } from '../../services/budget.service';
import { CategoryService, CategoryInfo } from '../../services/category.service';
import { ModalService } from '../../services/modal.service';

@Component({
  selector: 'app-budget-manager',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTableModule,
    MatIconModule,
    MatProgressBarModule
  ],
  templateUrl: './budget-manager.html',
  styleUrl: './budget-manager.scss'
})
export class BudgetManager implements OnInit {
  budgets: any[] = [];
  budgetProgress: any[] = [];
  displayedColumns: string[] = ['category', 'budgeted', 'spent', 'remaining', 'progress', 'actions'];
  
  newBudget = {
    category: '',
    amount: null
  };

  editingBudget: any = null;

  categories: CategoryInfo[] = [];

  constructor(
    private budgetService: BudgetService,
    public categoryService: CategoryService,
    private modalService: ModalService
  ) {
    this.categories = this.categoryService.getAllCategories();
  }

  ngOnInit() {
    this.loadBudgets();
    this.loadBudgetProgress();
  }

  get displayMonth(): string {
    if (this.budgetProgress && this.budgetProgress.length > 0) {
      return `${this.budgetProgress[0].month}/${this.budgetProgress[0].year}`;
    }
    const now = new Date();
    const month = now.getMonth() + 1;
    const year = now.getFullYear();
    return `${month}/${year}`;
  }

  loadBudgets() {
    this.budgetService.getBudgets().subscribe({
      next: (data) => {
        this.budgets = data;
      },
      error: (error) => console.error('Error loading budgets:', error)
    });
  }

  loadBudgetProgress() {
    this.budgetService.getBudgetProgress().subscribe({
      next: (data) => {
        this.budgetProgress = data;
      },
      error: (error) => console.error('Error loading budget progress:', error)
    });
  }

  addBudget() {
    if (!this.newBudget.category || !this.newBudget.amount) {
      this.modalService.showError('Please fill in all fields', 'Validation Error');
      return;
    }

    this.budgetService.createBudget(this.newBudget).subscribe({
      next: () => {
        this.loadBudgets();
        this.loadBudgetProgress();
        // Reset form
        this.newBudget = {
          category: '',
          amount: null
        };
      },
      error: (error) => {
        console.error('Error creating budget:', error);
        this.modalService.showError(error.error?.error || 'Failed to create budget');
      }
    });
  }

  startEdit(item: any) {
    this.editingBudget = { ...item };
  }

  saveEdit() {
    if (!this.editingBudget.amount || this.editingBudget.amount <= 0) {
      this.modalService.showError('Please enter a valid amount', 'Validation Error');
      return;
    }

    console.log('Saving budget:', this.editingBudget);  // Debug log

    this.budgetService.updateBudget(this.editingBudget.budget_id, {
      amount: this.editingBudget.amount
    }).subscribe({
      next: (response) => {
        console.log('Update successful:', response);  // Debug log
        this.editingBudget = null;
        this.loadBudgets();
        this.loadBudgetProgress();
      },
      error: (error) => {
        console.error('Error updating budget:', error);
        this.modalService.showError('Failed to update budget');
      }
    });
  }

  cancelEdit() {
    this.editingBudget = null;
  }

  async deleteBudget(id: number) {
    const confirmed = await this.modalService.showConfirm(
      'Are you sure you want to delete this budget? This is a recurring budget.',
      'Confirm Delete',
      'Delete',
      'Cancel'
    );

    if (confirmed) {
      this.budgetService.deleteBudget(id).subscribe({
        next: () => {
          this.loadBudgets();
          this.loadBudgetProgress();
        },
        error: (error) => console.error('Error deleting budget:', error)
      });
    }
  }

  getProgressColor(percentage: number): string {
    if (percentage < 50) return 'primary';
    if (percentage < 80) return 'accent';
    if (percentage < 100) return 'warn';
    return 'warn';
  }

  isOverBudget(item: any): boolean {
    return item.spent > item.budgeted;
  }

  isEditing(item: any): boolean {
    return this.editingBudget && this.editingBudget.budget_id === item.budget_id;
  }
}