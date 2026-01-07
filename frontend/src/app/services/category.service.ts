import { Injectable } from '@angular/core';

export interface CategoryInfo {
  value: string;
  displayName: string;
  color: string;
}

@Injectable({
  providedIn: 'root'
})
export class CategoryService {
  private readonly categories: CategoryInfo[] = [
    { value: 'INCOME', displayName: 'Income', color: 'rgba(74, 222, 128, 0.6)' },
    { value: 'TRANSFER_IN', displayName: 'Transfer In', color: 'rgba(96, 165, 250, 0.6)' },
    { value: 'TRANSFER_OUT', displayName: 'Transfer Out', color: 'rgba(129, 140, 248, 0.6)' },
    { value: 'LOAN_PAYMENTS', displayName: 'Loan Payments', color: 'rgba(248, 113, 113, 0.6)' },
    { value: 'BANK_FEES', displayName: 'Bank Fees', color: 'rgba(239, 68, 68, 0.6)' },
    { value: 'ENTERTAINMENT', displayName: 'Entertainment', color: 'rgba(192, 132, 252, 0.6)' },
    { value: 'FOOD_AND_DRINK', displayName: 'Food & Drink', color: 'rgba(251, 146, 60, 0.6)' },
    { value: 'GENERAL_MERCHANDISE', displayName: 'Shopping', color: 'rgba(244, 114, 182, 0.6)' },
    { value: 'HOME_IMPROVEMENT', displayName: 'Home Improvement', color: 'rgba(167, 139, 250, 0.6)' },
    { value: 'MEDICAL', displayName: 'Healthcare', color: 'rgba(45, 212, 191, 0.6)' },
    { value: 'PERSONAL_CARE', displayName: 'Personal Care', color: 'rgba(252, 165, 165, 0.6)' },
    { value: 'GENERAL_SERVICES', displayName: 'Services', color: 'rgba(34, 211, 238, 0.6)' },
    { value: 'GOVERNMENT_AND_NON_PROFIT', displayName: 'Government & Non-Profit', color: 'rgba(148, 163, 184, 0.6)' },
    { value: 'TRANSPORTATION', displayName: 'Transportation', color: 'rgba(251, 191, 36, 0.6)' },
    { value: 'TRAVEL', displayName: 'Travel', color: 'rgba(52, 211, 153, 0.6)' },
    { value: 'RENT_AND_UTILITIES', displayName: 'Rent & Utilities', color: 'rgba(56, 189, 248, 0.6)' }
  ];

  constructor() {}

  /**
   * Get all available categories
   */
  getAllCategories(): CategoryInfo[] {
    return this.categories;
  }

  /**
   * Get user-friendly display name from Plaid category
   */
  getCategoryDisplayName(value: string | null | undefined): string {
    if (!value) return 'Other';
    const cat = this.categories.find(c => c.value === value.toUpperCase());
    return cat ? cat.displayName : value;
  }

  /**
   * Get color rgba code from Plaid category
   */
  getCategoryColor(value: string | null | undefined): string {
    if (!value) return 'rgba(107, 114, 128, 0.6)';
    const cat = this.categories.find(c => c.value === value.toUpperCase());
    return cat ? cat.color : 'rgba(107, 114, 128, 0.6)';
  }

  /**
   * Get category metadata (display name and color)
   */
  getCategoryMetadata(value: string | null | undefined): { displayName: string, color: string } {
    return {
      displayName: this.getCategoryDisplayName(value),
      color: this.getCategoryColor(value)
    };
  }
}
