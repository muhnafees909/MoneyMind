import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

export interface PlaidAccount {
  id: number;
  name: string;
  official_name: string | null;
  account_type: string | null;
  account_subtype: string | null;
  mask: string | null;
  current_balance: number | null;
  available_balance: number | null;
  balance_updated_at: string | null;
  institution_name: string | null;
}

export interface EnvelopeSummary {
  goal_id: number;
  goal_name: string;
  target_amount: number;
  priority_order: number | null;
  envelope_balance: number;
  counter_drift: number;
}

export interface AccountReconciliation {
  account: PlaidAccount;
  envelopes: EnvelopeSummary[];
  allocated_total: number;
  actual_balance: number | null;
  unallocated_cash: number | null;
}

export interface SplitRow {
  goal_id: number;
  goal_name: string;
  amount: number;
  rule_type: string | null;
}

export interface IncomeEvent {
  id: number;
  transaction_id: number;
  amount: number;
  status: string;
  description: string | null;
  account_name: string | null;
  transaction_date: string | null;
  detected_at: string;
  suggested_split?: SplitRow[];
  unallocated_remainder?: number;
}

export interface AllocationRule {
  id: number;
  goal_id: number;
  goal_name: string | null;
  priority_order: number;
  allocation_type: 'fixed_amount' | 'percentage' | 'remainder';
  fixed_amount: number | null;
  percentage: number | null;
  is_active: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class EnvelopeService {
  private apiUrl = `${environment.apiUrl}/api/envelopes`;
  private plaidUrl = `${environment.apiUrl}/api/plaid`;

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

  getAccounts(): Observable<PlaidAccount[]> {
    return this.http.get<PlaidAccount[]>(`${this.apiUrl}/accounts`, {
      headers: this.getHeaders()
    });
  }

  syncAccounts(): Observable<any> {
    return this.http.post(`${this.plaidUrl}/sync-accounts`, {}, {
      headers: this.getHeaders()
    });
  }

  getReconciliation(): Observable<AccountReconciliation[]> {
    return this.http.get<AccountReconciliation[]>(`${this.apiUrl}/reconciliation`, {
      headers: this.getHeaders()
    });
  }

  createAllocation(
    goalId: number,
    amount: number,
    sourceType: 'manual' | 'withdrawal' | 'correction' = 'manual',
    note?: string
  ): Observable<any> {
    return this.http.post(
      `${this.apiUrl}/allocations`,
      { goal_id: goalId, amount, source_type: sourceType, note },
      { headers: this.getHeaders() }
    );
  }

  getAllocations(goalId?: number): Observable<any[]> {
    let params = new HttpParams();
    if (goalId) {
      params = params.set('goal_id', goalId);
    }
    return this.http.get<any[]>(`${this.apiUrl}/allocations`, {
      headers: this.getHeaders(),
      params
    });
  }

  // ----- Income events (paycheck prompt) -----

  getIncomeEvents(status: string = 'pending'): Observable<IncomeEvent[]> {
    return this.http.get<IncomeEvent[]>(`${this.apiUrl}/income-events`, {
      headers: this.getHeaders(),
      params: new HttpParams().set('status', status)
    });
  }

  scanIncomeEvents(): Observable<{ created: number }> {
    return this.http.post<{ created: number }>(`${this.apiUrl}/income-events/scan`, {}, {
      headers: this.getHeaders()
    });
  }

  confirmIncomeEvent(eventId: number, allocations: { goal_id: number; amount: number }[]): Observable<any> {
    return this.http.post(`${this.apiUrl}/income-events/${eventId}/confirm`,
      { allocations },
      { headers: this.getHeaders() });
  }

  dismissIncomeEvent(eventId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/income-events/${eventId}/dismiss`, {}, {
      headers: this.getHeaders()
    });
  }

  // ----- Allocation rules -----

  getRules(): Observable<AllocationRule[]> {
    return this.http.get<AllocationRule[]>(`${this.apiUrl}/rules`, {
      headers: this.getHeaders()
    });
  }

  createRule(rule: Partial<AllocationRule>): Observable<AllocationRule> {
    return this.http.post<AllocationRule>(`${this.apiUrl}/rules`, rule, {
      headers: this.getHeaders()
    });
  }

  updateRule(ruleId: number, changes: Partial<AllocationRule>): Observable<AllocationRule> {
    return this.http.put<AllocationRule>(`${this.apiUrl}/rules/${ruleId}`, changes, {
      headers: this.getHeaders()
    });
  }

  deleteRule(ruleId: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/rules/${ruleId}`, {
      headers: this.getHeaders()
    });
  }

  // ----- Envelope (goal) deletion -----

  deleteEnvelope(goalId: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/envelopes/${goalId}`, {
      headers: this.getHeaders()
    });
  }

  restoreEnvelope(goalId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/envelopes/${goalId}/restore`, {}, {
      headers: this.getHeaders()
    });
  }
}
