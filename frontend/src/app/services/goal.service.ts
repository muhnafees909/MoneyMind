import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class GoalService {
  private apiUrl = `${environment.apiUrl}/api/goals`;

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

  getGoals(): Observable<any> {
    return this.http.get(this.apiUrl, {
      headers: this.getHeaders()
    });
  }

  createGoal(goal: any): Observable<any> {
    return this.http.post(this.apiUrl, goal, {
      headers: this.getHeaders()
    });
  }

  updateGoal(id: number, goal: any): Observable<any> {
    return this.http.put(`${this.apiUrl}/${id}`, goal, {
      headers: this.getHeaders()
    });
  }

  addProgress(id: number, amount: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/${id}/add-progress`, { amount }, {
      headers: this.getHeaders()
    });
  }

  deleteGoal(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${id}`, {
      headers: this.getHeaders()
    });
  }
}