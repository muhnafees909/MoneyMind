import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

export interface CategoryInfo {
  value: string;
  displayName: string;
  color: string;
  icon?: string;
  isCustom?: boolean;
  id?: number;
}

// System defaults, hex colors (mirror the backend seed + shared/category-colors).
// Used as the initial cache so anything rendering before the API responds still
// shows correct names/colors; custom categories are merged in after fetch.
const DEFAULT_CATEGORIES: CategoryInfo[] = [
  { value: 'INCOME', displayName: 'Income', color: '#27b9de', icon: 'banknote' },
  { value: 'TRANSFER_IN', displayName: 'Transfer In', color: '#6c9de6', icon: 'arrow-down-left' },
  { value: 'TRANSFER_OUT', displayName: 'Transfer Out', color: '#b189e0', icon: 'arrow-up-right' },
  { value: 'LOAN_PAYMENTS', displayName: 'Loan Payments', color: '#8f93ea', icon: 'landmark' },
  { value: 'BANK_FEES', displayName: 'Bank Fees', color: '#8f93ea', icon: 'receipt' },
  { value: 'ENTERTAINMENT', displayName: 'Entertainment', color: '#b189e0', icon: 'clapperboard' },
  { value: 'FOOD_AND_DRINK', displayName: 'Food & Drink', color: '#e27c4e', icon: 'utensils' },
  { value: 'GENERAL_MERCHANDISE', displayName: 'Shopping', color: '#e07b9f', icon: 'shopping-bag' },
  { value: 'HOME_IMPROVEMENT', displayName: 'Home Improvement', color: '#a9bf49', icon: 'hammer' },
  { value: 'MEDICAL', displayName: 'Healthcare', color: '#a9bf49', icon: 'heart-pulse' },
  { value: 'PERSONAL_CARE', displayName: 'Personal Care', color: '#e07b9f', icon: 'sparkles' },
  { value: 'GENERAL_SERVICES', displayName: 'Services', color: '#e27c4e', icon: 'wrench' },
  { value: 'GOVERNMENT_AND_NON_PROFIT', displayName: 'Government & Non-Profit', color: '#dba43e', icon: 'building-2' },
  { value: 'TRANSPORTATION', displayName: 'Transportation', color: '#dba43e', icon: 'car' },
  { value: 'TRAVEL', displayName: 'Travel', color: '#27b9de', icon: 'plane' },
  { value: 'RENT_AND_UTILITIES', displayName: 'Rent & Utilities', color: '#6c9de6', icon: 'house' },
  { value: 'UNCATEGORIZED', displayName: 'Uncategorized', color: '#86817a', icon: 'circle-dashed' }
];

const OTHER_COLOR = '#86817a';

interface ApiCategory {
  id: number;
  value: string;
  display_name: string;
  color: string;
  icon: string;
  is_system: boolean;
  is_custom: boolean;
  archived: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class CategoryService {
  private apiUrl = `${environment.apiUrl}/api/categories`;
  private categories: CategoryInfo[] = [...DEFAULT_CATEGORIES];
  private byValue = new Map<string, CategoryInfo>(
    DEFAULT_CATEGORIES.map((c) => [c.value, c])
  );

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {
    // Warm the cache from the backend (includes the user's custom categories).
    this.refresh().subscribe({ error: () => {} });
  }

  private getHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({ Authorization: `Bearer ${token}` });
  }

  private index(list: CategoryInfo[]) {
    this.categories = list;
    this.byValue = new Map(list.map((c) => [c.value, c]));
  }

  /** Re-fetch categories (defaults + the user's custom) and update the cache. */
  refresh(): Observable<ApiCategory[]> {
    return this.http
      .get<ApiCategory[]>(this.apiUrl, { headers: this.getHeaders() })
      .pipe(
        tap((rows) =>
          this.index(
            rows.map((r) => ({
              value: r.value,
              displayName: r.display_name,
              color: r.color,
              icon: r.icon,
              isCustom: r.is_custom,
              id: r.id
            }))
          )
        )
      );
  }

  createCategory(name: string, color: string, icon: string): Observable<ApiCategory> {
    return this.http.post<ApiCategory>(
      this.apiUrl,
      { name, color, icon },
      { headers: this.getHeaders() }
    );
  }

  deleteCategory(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${id}`, { headers: this.getHeaders() });
  }

  /** All categories (system defaults + the user's custom), for pickers/lists. */
  getAllCategories(): CategoryInfo[] {
    return this.categories;
  }

  getCategoryDisplayName(value: string | null | undefined): string {
    if (!value) return 'Uncategorized';
    const cat = this.byValue.get(value) || this.byValue.get(value.toUpperCase());
    return cat ? cat.displayName : value;
  }

  getCategoryColor(value: string | null | undefined): string {
    if (!value) return OTHER_COLOR;
    const cat = this.byValue.get(value) || this.byValue.get(value.toUpperCase());
    return cat ? cat.color : OTHER_COLOR;
  }

  getCategoryIcon(value: string | null | undefined): string {
    if (!value) return 'circle-dashed';
    const cat = this.byValue.get(value) || this.byValue.get(value.toUpperCase());
    return cat?.icon || 'tag';
  }

  getCategoryMetadata(value: string | null | undefined): { displayName: string; color: string } {
    return {
      displayName: this.getCategoryDisplayName(value),
      color: this.getCategoryColor(value)
    };
  }
}
