/**
 * Type definitions for the AI Financial Advisor Chat feature
 */

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ContextUsed {
  budgets_count: number;
  active_goals: number;
  completed_goals: number;
  monthly_spending: number;
  categories_analyzed: number;
  recent_transactions_analyzed: number;
  model_used: string;
}

export interface ChatResponse {
  response: string;
  context_used: ContextUsed;
}

export interface ChatError {
  error: string;
}

export interface ChatRequest {
  message: string;
  history?: Pick<ChatMessage, 'role' | 'content'>[];
}
