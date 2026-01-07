import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { AuthService } from './auth.service';
import { Observable } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';
import { throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { LoggerService } from './logger.service';

@Injectable({
  providedIn: 'root'
})
export class TransactionService {

  private apiUrl = `${environment.apiUrl}/api`;

  constructor(
    private http: HttpClient,
    private authService: AuthService,
    private logger: LoggerService
  ) {
    this.logger.info('TransactionService initialized', 'TransactionService');
  }

  private getHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });
  }

  getSpendingByCategory(): Observable<any> {
    this.logger.debug('Fetching spending by category', 'TransactionService');
    this.logger.apiRequest('GET', `${this.apiUrl}/analytics/spending-by-category`);

    return this.http.get(`${this.apiUrl}/analytics/spending-by-category`, {
      headers: this.getHeaders()
    }).pipe(
      tap((data: any) => {
        this.logger.success(`Loaded ${data.length} categories`, 'TransactionService', data);
        this.logger.apiResponse('GET', `${this.apiUrl}/analytics/spending-by-category`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to fetch spending by category', 'TransactionService', error);
        this.logger.apiError('GET', `${this.apiUrl}/analytics/spending-by-category`, error);
        return throwError(() => error);
      })
    );
  }

  getMonthlySpending(): Observable<any> {
    this.logger.debug('Fetching monthly spending', 'TransactionService');
    this.logger.apiRequest('GET', `${this.apiUrl}/analytics/monthly-spending`);

    return this.http.get(`${this.apiUrl}/analytics/monthly-spending`, {
      headers: this.getHeaders()
    }).pipe(
      tap((data: any) => {
        this.logger.success(`Loaded ${data.length} months of spending data`, 'TransactionService');
        this.logger.apiResponse('GET', `${this.apiUrl}/analytics/monthly-spending`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to fetch monthly spending', 'TransactionService', error);
        this.logger.apiError('GET', `${this.apiUrl}/analytics/monthly-spending`, error);
        return throwError(() => error);
      })
    );
  }

  getSpendingSummary(): Observable<any> {
    this.logger.debug('Fetching spending summary', 'TransactionService');
    this.logger.apiRequest('GET', `${this.apiUrl}/analytics/spending-summary`);

    return this.http.get(`${this.apiUrl}/analytics/spending-summary`, {
      headers: this.getHeaders()
    }).pipe(
      tap((data: any) => {
        this.logger.success('Spending summary loaded', 'TransactionService', data);
        this.logger.apiResponse('GET', `${this.apiUrl}/analytics/spending-summary`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to fetch spending summary', 'TransactionService', error);
        this.logger.apiError('GET', `${this.apiUrl}/analytics/spending-summary`, error);
        return throwError(() => error);
      })
    );
  }

  getSpendingByCategoryMonthly(): Observable<any> {
    this.logger.debug('Fetching monthly spending by category', 'TransactionService');
    this.logger.apiRequest('GET', `${this.apiUrl}/analytics/spending-by-category/monthly`);

    return this.http.get(`${this.apiUrl}/analytics/spending-by-category/monthly`, {
      headers: this.getHeaders()
    }).pipe(
      tap((data: any) => {
        this.logger.success(`Loaded ${data.length} categories for current month`, 'TransactionService', data);
        this.logger.apiResponse('GET', `${this.apiUrl}/analytics/spending-by-category/monthly`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to fetch monthly spending by category', 'TransactionService', error);
        this.logger.apiError('GET', `${this.apiUrl}/analytics/spending-by-category/monthly`, error);
        return throwError(() => error);
      })
    );
  }

  getSpendingSummaryMonthly(): Observable<any> {
    this.logger.debug('Fetching monthly spending summary', 'TransactionService');
    this.logger.apiRequest('GET', `${this.apiUrl}/analytics/spending-summary/monthly`);

    return this.http.get(`${this.apiUrl}/analytics/spending-summary/monthly`, {
      headers: this.getHeaders()
    }).pipe(
      tap((data: any) => {
        this.logger.success('Monthly spending summary loaded', 'TransactionService', data);
        this.logger.apiResponse('GET', `${this.apiUrl}/analytics/spending-summary/monthly`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to fetch monthly spending summary', 'TransactionService', error);
        this.logger.apiError('GET', `${this.apiUrl}/analytics/spending-summary/monthly`, error);
        return throwError(() => error);
      })
    );
  }

  createTransaction(transaction: any): Observable<any> {
    this.logger.info('Creating new transaction', 'TransactionService', transaction);
    this.logger.apiRequest('POST', `${this.apiUrl}/transactions/`, transaction);

    return this.http.post(`${this.apiUrl}/transactions/`, transaction, {
      headers: this.getHeaders()
    }).pipe(
      tap((data: any) => {
        this.logger.success(`Transaction created with ID: ${data.id}`, 'TransactionService', data);
        this.logger.apiResponse('POST', `${this.apiUrl}/transactions/`, 201);
      }),
      catchError(error => {
        this.logger.error('Failed to create transaction', 'TransactionService', error);
        this.logger.apiError('POST', `${this.apiUrl}/transactions/`, error);
        return throwError(() => error);
      })
    );
  }
  
  updateTransaction(id: number, transaction: any): Observable<any> {
    this.logger.info(`Updating transaction ID: ${id}`, 'TransactionService', transaction);
    this.logger.apiRequest('PUT', `${this.apiUrl}/transactions/${id}`, transaction);

    return this.http.put(`${this.apiUrl}/transactions/${id}`, transaction, {
      headers: this.getHeaders()
    }).pipe(
      tap(() => {
        this.logger.success(`Transaction ${id} updated successfully`, 'TransactionService');
        this.logger.apiResponse('PUT', `${this.apiUrl}/transactions/${id}`, 200);
      }),
      catchError(error => {
        this.logger.error(`Failed to update transaction ${id}`, 'TransactionService', error);
        this.logger.apiError('PUT', `${this.apiUrl}/transactions/${id}`, error);
        return throwError(() => error);
      })
    );
  }
  
  deleteTransaction(id: number): Observable<any> {
    this.logger.warn(`Deleting transaction ID: ${id}`, 'TransactionService');
    this.logger.apiRequest('DELETE', `${this.apiUrl}/transactions/${id}`);

    return this.http.delete(`${this.apiUrl}/transactions/${id}`, {
      headers: this.getHeaders()
    }).pipe(
      tap(() => {
        this.logger.success(`Transaction ${id} deleted successfully`, 'TransactionService');
        this.logger.apiResponse('DELETE', `${this.apiUrl}/transactions/${id}`, 200);
      }),
      catchError(error => {
        this.logger.error(`Failed to delete transaction ${id}`, 'TransactionService', error);
        this.logger.apiError('DELETE', `${this.apiUrl}/transactions/${id}`, error);
        return throwError(() => error);
      })
    );
  }
  
  getTransactions(): Observable<any> {
    this.logger.debug('Fetching all transactions', 'TransactionService');
    this.logger.apiRequest('GET', `${this.apiUrl}/transactions/`);

    return this.http.get(`${this.apiUrl}/transactions/`, {
      headers: this.getHeaders()
    }).pipe(
      tap((data: any) => {
        this.logger.success(`Loaded ${data.length} transactions`, 'TransactionService');
        this.logger.apiResponse('GET', `${this.apiUrl}/transactions/`, 200);
      }),
      catchError(error => {
        this.logger.error('Failed to fetch transactions', 'TransactionService', error);
        this.logger.apiError('GET', `${this.apiUrl}/transactions/`, error);
        return throwError(() => error);
      })
    );
  }
}
