import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = `${environment.apiUrl}/api/auth`;
  private plaidApiUrl = `${environment.apiUrl}/api/plaid`;

  constructor(private http: HttpClient) { }

  login(email: string, password: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/login`, { email, password });
  }

  register(registrationData: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/register`, registrationData);
  }

  saveToken(token: string): void {
    localStorage.setItem('access_token', token);
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  logout(): void {
    localStorage.removeItem('access_token');
  }

  createLinkToken(): Observable<any> {
    const token = this.getToken()

    return this.http.post(`${this.plaidApiUrl}/create-link-token`, {}, {
      headers: new HttpHeaders({
        'Authorization': `Bearer ${token}`
      })
    });
  }

  exchangePublicToken(publicToken: string): Observable<any> {
    const token = this.getToken();
    return this.http.post(`${this.plaidApiUrl}/exchange-public-token`,
      { public_token: publicToken },
      {
        headers: new HttpHeaders({
          'Authorization': `Bearer ${token}`
        })
      }
    );
  }
  
  syncTransactions(accessToken: string): Observable<any> {
    const token = this.getToken();
    return this.http.post(`${this.plaidApiUrl}/sync-transactions`,
      { access_token: accessToken },
      {
        headers: new HttpHeaders({
          'Authorization': `Bearer ${token}`
        })
      }
    );
  }

}