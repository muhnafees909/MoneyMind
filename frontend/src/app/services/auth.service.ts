import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = 'http://localhost:5000/api/auth';

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

    return this.http.post('http://localhost:5000/api/plaid/create-link-token', {}, {
      headers: new HttpHeaders({
        'Authorization': `Bearer ${token}`
      })
    });
  }

  exchangePublicToken(publicToken: string): Observable<any> {
    const token = this.getToken();
    return this.http.post('http://localhost:5000/api/plaid/exchange-public-token', 
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
    return this.http.post('http://localhost:5000/api/plaid/sync-transactions',
      { access_token: accessToken },
      {
        headers: new HttpHeaders({
          'Authorization': `Bearer ${token}`
        })
      }
    );
  }

}