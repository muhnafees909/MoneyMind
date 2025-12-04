import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { AuthService } from './auth.service';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class TransactionService {
  
  private apiUrl = 'http://localhost:5000/api';

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });
  }

  getSpendingByCategory(): Observable<any> {
    return this.http.get(`${this.apiUrl}/analytics/spending-by-category`, {
      headers: this.getHeaders()
    })
  }

  getMonthlySpending(): Observable<any> {
    return this.http.get(`${this.apiUrl}/analytics/monthly-spending`, {
      headers: this.getHeaders()
    })
  }

  getSpendingSummary(): Observable<any> {
    return this.http.get(`${this.apiUrl}/analytics/spending-summary`, {
      headers: this.getHeaders()
    });
  }

  createTransaction(transaction: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/transactions/`, transaction, {
      headers: this.getHeaders()
    });
  }
  
  updateTransaction(id: number, transaction: any): Observable<any> {
    return this.http.put(`${this.apiUrl}/transactions/${id}`, transaction, {
      headers: this.getHeaders()
    });
  }
  
  deleteTransaction(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/transactions/${id}`, {
      headers: this.getHeaders()
    });
  }
  
  getTransactions(): Observable<any> {
    return this.http.get(`${this.apiUrl}/transactions/`, {
      headers: this.getHeaders()
    });
  }
}
