import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class BudgetService {
  private apiUrl = `${environment.apiUrl}/api/budgets`;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) { }

  private getHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });
  }

  getBudgets(): Observable<any> {
    return this.http.get(this.apiUrl, {
      headers: this.getHeaders()
    });
  }

  createBudget(budget: any): Observable<any> {
    return this.http.post(this.apiUrl, budget, {
      headers: this.getHeaders()
    });
  }

  updateBudget(id: number, budget: any): Observable<any> {
    return this.http.put(`${this.apiUrl}/${id}`, budget, {
      headers: this.getHeaders()
    });
  }

  deleteBudget(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${id}`, {
      headers: this.getHeaders()
    });
  }

  getBudgetProgress(month?: number, year?: number): Observable<any> {
    let url = `${this.apiUrl}/progress`;
    if (month && year) {
      url += `?month=${month}&year=${year}`;
    }
    return this.http.get(url, {
      headers: this.getHeaders()
    });
  }
}