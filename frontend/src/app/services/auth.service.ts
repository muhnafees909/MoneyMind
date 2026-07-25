import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { LoggerService } from './logger.service';

export interface AuthUser {
  id: number;
  email: string;
  first_name: string;
  email_verified: boolean;
  mfa_enabled: boolean;
}

export interface LoginResult {
  user?: AuthUser;
  mfa_required?: boolean;
  mfa_token?: string;
}

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

  // Emits whenever the signed-in state changes, so the SessionService can
  // start/stop its expiry timer without AuthService depending on it.
  private authState = new BehaviorSubject<boolean>(this.isLoggedIn());
  readonly authState$ = this.authState.asObservable();

  // Current user (verification + MFA state), for the banner and gating.
  readonly currentUser = signal<AuthUser | null>(null);

  constructor(
    private http: HttpClient,
    private logger: LoggerService
  ) {}

  /**
   * Password step. If the account has MFA, the response carries
   * { mfa_required, mfa_token } and NO session is established yet — the caller
   * must complete completeMfaLogin(). Otherwise a session is issued.
   */
  login(email: string, password: string): Observable<LoginResult> {
    return this.http.post<LoginResult>(`${this.apiUrl}/login`, { email, password }).pipe(
      tap((res) => {
        if (res.user) {
          this.currentUser.set(res.user);
          this.markAuthed();
          this.logger.info('Signed in', 'AuthService');
        }
      })
    );
  }

  /** Second login step: submit the TOTP/backup code with the pending token. */
  completeMfaLogin(mfaToken: string, code: string): Observable<LoginResult> {
    return this.http
      .post<LoginResult>(`${this.apiUrl}/login/mfa`, { mfa_token: mfaToken, code })
      .pipe(
        tap((res) => {
          if (res.user) {
            this.currentUser.set(res.user);
            this.markAuthed();
          }
        })
      );
  }

  register(registrationData: any): Observable<LoginResult> {
    return this.http.post<LoginResult>(`${this.apiUrl}/register`, registrationData).pipe(
      tap((res) => {
        if (res.user) {
          this.currentUser.set(res.user);
        }
        this.markAuthed();
        this.logger.info('Account created', 'AuthService');
      })
    );
  }

  /** Refresh the cached user (verification + MFA flags) from the server. */
  loadCurrentUser(): Observable<AuthUser> {
    return this.http
      .get<AuthUser>(`${this.apiUrl}/me`)
      .pipe(tap((u) => this.currentUser.set(u)));
  }

  // ----- Email verification -----

  verifyEmail(token: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/verify-email`, { token });
  }

  resendVerification(): Observable<any> {
    return this.http.post(`${this.apiUrl}/verify-email/resend`, {});
  }

  // ----- MFA management -----

  mfaStatus(): Observable<{ mfa_enabled: boolean; backup_codes_remaining: number }> {
    return this.http.get<{ mfa_enabled: boolean; backup_codes_remaining: number }>(
      `${this.apiUrl}/mfa/status`
    );
  }

  mfaSetup(): Observable<{ secret: string; otpauth_uri: string; qr_data_uri: string }> {
    return this.http.post<{ secret: string; otpauth_uri: string; qr_data_uri: string }>(
      `${this.apiUrl}/mfa/setup`,
      {}
    );
  }

  mfaConfirm(code: string): Observable<{ backup_codes: string[] }> {
    return this.http.post<{ backup_codes: string[] }>(`${this.apiUrl}/mfa/confirm`, { code });
  }

  mfaDisable(password: string, code: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/mfa/disable`, { password, code });
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
    this.authState.next(true);
  }

  clearSession(): void {
    localStorage.removeItem(AUTH_HINT_KEY);
    localStorage.removeItem('access_token');
    this.currentUser.set(null);
    this.authState.next(false);
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
