import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { PlaidAccount } from './envelope.service';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AccountService {
  private apiUrl = `${environment.apiUrl}/api/accounts`;
  private plaidUrl = `${environment.apiUrl}/api/plaid`;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({ Authorization: `Bearer ${token}` });
  }

  getAccounts(): Observable<PlaidAccount[]> {
    return this.http.get<PlaidAccount[]>(this.apiUrl, { headers: this.getHeaders() });
  }

  /** Set or clear an account's nickname. Pass '' or null to revert to the Plaid name. */
  rename(accountId: number, nickname: string | null): Observable<PlaidAccount> {
    return this.http.patch<PlaidAccount>(
      `${this.apiUrl}/${accountId}`,
      { nickname },
      { headers: this.getHeaders() }
    );
  }

  /** Refresh account list + balances from the connected banks. */
  syncAccounts(): Observable<{ message: string; accounts: PlaidAccount[] }> {
    return this.http.post<{ message: string; accounts: PlaidAccount[] }>(
      `${this.plaidUrl}/sync-accounts`,
      {},
      { headers: this.getHeaders() }
    );
  }
}
