import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

export interface RecurringOccurrence {
  id: number;
  transaction_id: number;
  amount: number;
  occurred_at: string;
}

export interface PriceCreep {
  previous_average: number;
  latest_amount: number;
  increase_pct: number;
}

export interface RecurringExpense {
  id: number;
  merchant_name: string;
  category: string | null;
  expected_amount: number;
  monthly_equivalent: number;
  cadence: 'weekly' | 'biweekly' | 'monthly' | 'annual';
  next_expected_date: string | null;
  status: string;
  confirmed_by_user: boolean;
  detected_at: string;
  occurrence_count: number;
  last_amount: number | null;
  last_occurred_at: string | null;
  price_creep: PriceCreep | null;
  occurrences?: RecurringOccurrence[];
}

export interface RecurringCategorySummary {
  category: string;
  monthly_total: number;
  count: number;
}

export interface RecurringSummary {
  total_monthly: number;
  categories: RecurringCategorySummary[];
}

@Injectable({
  providedIn: 'root'
})
export class RecurringService {
  private apiUrl = `${environment.apiUrl}/api/recurring`;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      Authorization: `Bearer ${token}`
    });
  }

  detect(): Observable<{ new_candidates: number; new_occurrences: number }> {
    return this.http.post<{ new_candidates: number; new_occurrences: number }>(
      `${this.apiUrl}/detect`, {}, { headers: this.getHeaders() });
  }

  getRecurring(status: 'review' | 'confirmed' | 'all' = 'all'): Observable<RecurringExpense[]> {
    return this.http.get<RecurringExpense[]>(this.apiUrl, {
      headers: this.getHeaders(),
      params: new HttpParams().set('status', status)
    });
  }

  confirm(id: number, category?: string): Observable<RecurringExpense> {
    return this.http.post<RecurringExpense>(`${this.apiUrl}/${id}/confirm`,
      category ? { category } : {},
      { headers: this.getHeaders() });
  }

  dismiss(id: number): Observable<RecurringExpense> {
    return this.http.post<RecurringExpense>(`${this.apiUrl}/${id}/dismiss`, {}, {
      headers: this.getHeaders()
    });
  }

  update(id: number, changes: Partial<RecurringExpense>): Observable<RecurringExpense> {
    return this.http.put<RecurringExpense>(`${this.apiUrl}/${id}`, changes, {
      headers: this.getHeaders()
    });
  }

  getSummary(): Observable<RecurringSummary> {
    return this.http.get<RecurringSummary>(`${this.apiUrl}/summary`, {
      headers: this.getHeaders()
    });
  }

  createManual(data: {
    category: string;
    expected_amount: number;
    cadence: 'weekly' | 'biweekly' | 'monthly' | 'annual';
    description?: string;
  }): Observable<RecurringExpense> {
    return this.http.post<RecurringExpense>(`${this.apiUrl}/manual`, data, {
      headers: this.getHeaders()
    });
  }
}
