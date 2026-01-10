import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';
import { throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { LoggerService } from './logger.service';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = `${environment.apiUrl}/api/auth`;
  private plaidApiUrl = `${environment.apiUrl}/api/plaid`;

  constructor(
    private http: HttpClient,
    private logger: LoggerService
  ) {
    this.logger.info('AuthService initialized', 'AuthService');
  }

  login(email: string, password: string): Observable<any> {
    this.logger.info(`Attempting login for user: ${email}`, 'AuthService');
    this.logger.apiRequest('POST', `${this.apiUrl}/login`, { email });

    return this.http.post(`${this.apiUrl}/login`, { email, password }).pipe(
      tap((response: any) => {
        this.logger.success('Login successful', 'AuthService', { email });
        this.logger.apiResponse('POST', `${this.apiUrl}/login`, 200, { hasToken: !!response.access_token });
      }),
      catchError(error => {
        this.logger.error('Login failed', 'AuthService', error);
        this.logger.apiError('POST', `${this.apiUrl}/login`, error);
        return throwError(() => error);
      })
    );
  }

  register(registrationData: any): Observable<any> {
    this.logger.info(`Attempting registration for user: ${registrationData.email}`, 'AuthService');
    this.logger.apiRequest('POST', `${this.apiUrl}/register`, { email: registrationData.email });

    return this.http.post(`${this.apiUrl}/register`, registrationData).pipe(
      tap(() => {
        this.logger.success('Registration successful', 'AuthService', { email: registrationData.email });
        this.logger.apiResponse('POST', `${this.apiUrl}/register`, 201);
      }),
      catchError(error => {
        this.logger.error('Registration failed', 'AuthService', error);
        this.logger.apiError('POST', `${this.apiUrl}/register`, error);
        return throwError(() => error);
      })
    );
  }

  saveToken(token: string): void {
    this.logger.debug('Saving JWT token to localStorage', 'AuthService');
    localStorage.setItem('access_token', token);
    this.logger.info('JWT token saved successfully', 'AuthService');
  }

  getToken(): string | null {
    const token = localStorage.getItem('access_token');
    this.logger.debug(`Token retrieval: ${token ? 'found' : 'not found'}`, 'AuthService');
    return token;
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  logout(): void {
    this.logger.info('User logging out', 'AuthService');
    localStorage.removeItem('access_token');
    this.logger.success('User logged out successfully', 'AuthService');
  }

  createLinkToken(): Observable<any> {
    this.logger.info('Creating Plaid link token', 'AuthService.Plaid');
    const token = this.getToken();
    this.logger.apiRequest('POST', `${this.plaidApiUrl}/create-link-token`);

    return this.http.post(`${this.plaidApiUrl}/create-link-token`, {}, {
      headers: new HttpHeaders({
        'Authorization': `Bearer ${token}`
      })
    }).pipe(
      tap(() => {
        this.logger.success('Plaid link token created', 'AuthService.Plaid');
        this.logger.apiResponse('POST', `${this.plaidApiUrl}/create-link-token`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to create Plaid link token', 'AuthService.Plaid', error);
        this.logger.apiError('POST', `${this.plaidApiUrl}/create-link-token`, error);
        return throwError(() => error);
      })
    );
  }

  exchangePublicToken(publicToken: string): Observable<any> {
    this.logger.info('Exchanging Plaid public token', 'AuthService.Plaid');
    const token = this.getToken();
    this.logger.apiRequest('POST', `${this.plaidApiUrl}/exchange-public-token`);

    return this.http.post(`${this.plaidApiUrl}/exchange-public-token`,
      { public_token: publicToken },
      {
        headers: new HttpHeaders({
          'Authorization': `Bearer ${token}`
        })
      }
    ).pipe(
      tap(() => {
        this.logger.success('Plaid public token exchanged successfully', 'AuthService.Plaid');
        this.logger.apiResponse('POST', `${this.plaidApiUrl}/exchange-public-token`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to exchange Plaid public token', 'AuthService.Plaid', error);
        this.logger.apiError('POST', `${this.plaidApiUrl}/exchange-public-token`, error);
        return throwError(() => error);
      })
    );
  }
  
  syncTransactions(accessToken?: string): Observable<any> {
    this.logger.info('Syncing Plaid transactions', 'AuthService.Plaid');
    const token = this.getToken();
    this.logger.apiRequest('POST', `${this.plaidApiUrl}/sync-transactions`);

    // accessToken is now optional - backend will fetch from database if not provided
    const body = accessToken ? { access_token: accessToken } : {};

    return this.http.post(`${this.plaidApiUrl}/sync-transactions`,
      body,
      {
        headers: new HttpHeaders({
          'Authorization': `Bearer ${token}`
        })
      }
    ).pipe(
      tap((response: any) => {
        this.logger.success(`Synced ${response.saved_transactions || 0} transactions`, 'AuthService.Plaid', response);
        this.logger.apiResponse('POST', `${this.plaidApiUrl}/sync-transactions`, 200, response);
      }),
      catchError(error => {
        this.logger.error('Failed to sync Plaid transactions', 'AuthService.Plaid', error);
        this.logger.apiError('POST', `${this.plaidApiUrl}/sync-transactions`, error);
        return throwError(() => error);
      })
    );
  }

  cleanupDuplicates(): Observable<any> {
    this.logger.info('Cleaning up duplicate transactions and PlaidItems', 'AuthService.Plaid');
    const token = this.getToken();
    this.logger.apiRequest('POST', `${this.plaidApiUrl}/cleanup-duplicates`);

    return this.http.post(`${this.plaidApiUrl}/cleanup-duplicates`, {}, {
      headers: new HttpHeaders({
        'Authorization': `Bearer ${token}`
      })
    }).pipe(
      tap((response: any) => {
        this.logger.success('Cleanup completed', 'AuthService.Plaid', response);
        this.logger.apiResponse('POST', `${this.plaidApiUrl}/cleanup-duplicates`, 200, response);
      }),
      catchError(error => {
        this.logger.error('Cleanup failed', 'AuthService.Plaid', error);
        this.logger.apiError('POST', `${this.plaidApiUrl}/cleanup-duplicates`, error);
        return throwError(() => error);
      })
    );
  }

}