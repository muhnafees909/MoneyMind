import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatResponse {
  response: string;
  context_used: {
    budgets_count: number;
    active_goals: number;
    completed_goals: number;
    monthly_spending: number;
    categories_analyzed: number;
    recent_transactions_analyzed: number;
    model_used: string;
  };
}

export interface ChatError {
  error: string;
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private apiUrl = `${environment.apiUrl}/api/chat`;

  constructor(
    private http: HttpClient,
    private authService: AuthService
  ) {}

  private getHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    });
  }

  sendMessage(message: string, history: ChatMessage[] = []): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(
      `${this.apiUrl}/message`,
      {
        message,
        history: history.map(({ role, content }) => ({ role, content }))
      },
      { headers: this.getHeaders() }
    );
  }
}
