import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';
import { GoalService } from '../../services/goal.service';

@Component({
  selector: 'app-goals-manager',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatIconModule,
    MatProgressBarModule,
    MatChipsModule
  ],
  templateUrl: './goals-manager.html',
  styleUrl: './goals-manager.scss'
})
export class GoalsManagerComponent implements OnInit {
  goals: any[] = [];
  activeGoals: any[] = [];
  completedGoals: any[] = [];
  
  newGoal = {
    name: '',
    description: '',
    target_amount: null,
    current_amount: 0,
    target_date: null
  };

  addingProgress: { [key: number]: number } = {};
  editingGoal: any = null;

  constructor(private goalService: GoalService) {}

  ngOnInit() {
    this.loadGoals();
  }

  loadGoals() {
    this.goalService.getGoals().subscribe({
      next: (data) => {
        console.log('RAW GOAL DATA:', JSON.stringify(data, null, 2));  // DEBUG
        this.goals = data;
        this.activeGoals = data.filter((g: any) => !g.is_completed);
        this.completedGoals = data.filter((g: any) => g.is_completed);
      },
      error: (error) => console.error('Error loading goals:', error)
    });
  }
  
  formatCompletedDate(dateStr: string): string {
    // Extract just the date part and format it
    const datePart = dateStr.split('T')[0];
    const [year, month, day] = datePart.split('-');
    const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  createGoal() {
    if (!this.newGoal.name || !this.newGoal.target_amount) {
      alert('Please fill in name and target amount');
      return;
    }
  
    const goalData = {
      ...this.newGoal,
      target_date: this.newGoal.target_date ? 
        this.formatDate(new Date(this.newGoal.target_date)) : null
    };
  
    this.goalService.createGoal(goalData).subscribe({
      next: () => {
        this.loadGoals();
        // Reset form
        this.newGoal = {
          name: '',
          description: '',
          target_amount: null,
          current_amount: 0,
          target_date: null
        };
      },
      error: (error) => {
        console.error('Error creating goal:', error);
        alert('Failed to create goal');
      }
    });
  }

  parseCompletedDate(dateStr: string): Date {
    // Parse as date only to avoid timezone issues
    const [year, month, day] = dateStr.split('-').map(Number);
    return new Date(year, month - 1, day);
  }

  addProgressToGoal(goalId: number) {
    const amount = this.addingProgress[goalId];
    
    if (!amount || amount <= 0) {
      alert('Please enter a valid amount');
      return;
    }

    this.goalService.addProgress(goalId, amount).subscribe({
      next: () => {
        this.loadGoals();
        this.addingProgress[goalId] = 0;
      },
      error: (error) => {
        console.error('Error adding progress:', error);
        alert('Failed to add progress');
      }
    });
  }

  startEdit(goal: any) {
    this.editingGoal = { 
      ...goal,
      target_date: goal.target_date ? this.parseDate(goal.target_date) : null
    };
  }

  // Add this new helper method
  parseDate(dateStr: string): Date {
    // Parse the date string as UTC to avoid timezone shifts
    const [year, month, day] = dateStr.split('-').map(Number);
    return new Date(year, month - 1, day);  // month is 0-indexed in JS
  }

  cancelEdit() {
    this.editingGoal = null;
  }

  saveEdit() {
    if (!this.editingGoal.name || !this.editingGoal.target_amount) {
      alert('Please fill in required fields');
      return;
    }
  
    const updateData = {
      name: this.editingGoal.name,
      description: this.editingGoal.description,
      target_amount: this.editingGoal.target_amount,
      current_amount: this.editingGoal.current_amount,
      target_date: this.editingGoal.target_date ? 
        this.formatDate(this.editingGoal.target_date) : null
    };
  
    this.goalService.updateGoal(this.editingGoal.id, updateData).subscribe({
      next: () => {
        this.loadGoals();
        this.editingGoal = null;
      },
      error: (error) => {
        console.error('Error updating goal:', error);
        alert('Failed to update goal');
      }
    });
  }
  
  // Add this new helper method
  formatDate(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  deleteGoal(id: number, name: string) {
    if (confirm(`Are you sure you want to delete "${name}"?`)) {
      this.goalService.deleteGoal(id).subscribe({
        next: () => {
          this.loadGoals();
        },
        error: (error) => console.error('Error deleting goal:', error)
      });
    }
  }

  getProgressColor(percentage: number): string {
    if (percentage < 33) return 'warn';
    if (percentage < 66) return 'accent';
    return 'primary';
  }

  getDaysRemaining(targetDate: string): number | null {
    if (!targetDate) return null;
    const target = new Date(targetDate);
    const today = new Date();
    const diff = target.getTime() - today.getTime();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  }

  isEditing(goal: any): boolean {
    return this.editingGoal && this.editingGoal.id === goal.id;
  }
}

