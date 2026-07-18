import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { LoggerService } from './logger.service';

/**
 * Session auth over secure httpOnly cookies.
 *
 * The browser never sees the tokens: the server sets/clears them as
 * httpOnly cookies, and the auth interceptor sends them (plus the CSRF
 * header) on every API call. The only thing stored client-side is a
 * non-sensitive "signed in" hint used for instant route-guard decisions —
 * it is NOT a credential; the backend enforces everything.
 */
const AUTH_HINT_KEY = 'mm_authed';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = `${environment.apiUrl}/api/auth`;
  private plaidApiUrl = `${environment.apiUrl}/api/plaid`;

  constructor(
    private http: HttpClient,
    private logger: LoggerService
  ) {}

  login(email: string, password: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/login`, { email, password }).pipe(
      tap(() => {
        this.markAuthed();
        this.logger.info('Signed in', 'AuthService');
      })
    );
  }

  register(registrationData: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/register`, registrationData).pipe(
      tap(() => {
        this.markAuthed();
        this.logger.info('Account created', 'AuthService');
      })
    );
  }

  logout(): void {
    // Clear the local hint immediately; the server clears the cookies.
    this.clearSession();
    this.http.post(`${this.apiUrl}/logout`, {}).subscribe({
      error: () => {
        // Cookies may already be expired — signing out locally is enough
      }
    });
  }

  isLoggedIn(): boolean {
    return localStorage.getItem(AUTH_HINT_KEY) === '1';
  }

  markAuthed(): void {
    localStorage.setItem(AUTH_HINT_KEY, '1');
    // Remove any token a previous version of the app left behind
    localStorage.removeItem('access_token');
  }

  clearSession(): void {
    localStorage.removeItem(AUTH_HINT_KEY);
    localStorage.removeItem('access_token');
  }

  /**
   * @deprecated Sessions live in httpOnly cookies now; there is no
   * client-readable token. Kept so older service code compiles — the auth
   * interceptor strips any Authorization header it produces.
   */
  getToken(): string | null {
    return null;
  }

  // ----- Plaid (cookies + CSRF handled by the interceptor) -----

  createLinkToken(): Observable<any> {
    return this.http.post(`${this.plaidApiUrl}/create-link-token`, {});
  }

  exchangePublicToken(publicToken: string): Observable<any> {
    return this.http.post(`${this.plaidApiUrl}/exchange-public-token`, {
      public_token: publicToken
    });
  }

  syncTransactions(accessToken?: string): Observable<any> {
    const body = accessToken ? { access_token: accessToken } : {};
    return this.http.post(`${this.plaidApiUrl}/sync-transactions`, body);
  }
}
