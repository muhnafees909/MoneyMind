import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4
}

@Injectable({
  providedIn: 'root'
})
export class LoggerService {
  private logLevel: LogLevel = environment.production ? LogLevel.WARN : LogLevel.DEBUG;
  private readonly styles = {
    debug: 'color: #64748b; font-weight: normal',
    info: 'color: #3b82f6; font-weight: bold',
    warn: 'color: #eab308; font-weight: bold',
    error: 'color: #ef4444; font-weight: bold',
    success: 'color: #22c55e; font-weight: bold'
  };

  debug(message: string, context?: string, data?: any): void {
    if (this.logLevel <= LogLevel.DEBUG) {
      const timestamp = new Date().toISOString();
      console.log(
        `%c[${timestamp}] [DEBUG] ${context ? `[${context}]` : ''} ${message}`,
        this.styles.debug,
        data || ''
      );
    }
  }

  info(message: string, context?: string, data?: any): void {
    if (this.logLevel <= LogLevel.INFO) {
      const timestamp = new Date().toISOString();
      console.log(
        `%c[${timestamp}] [INFO] ${context ? `[${context}]` : ''} ${message}`,
        this.styles.info,
        data || ''
      );
    }
  }

  success(message: string, context?: string, data?: any): void {
    if (this.logLevel <= LogLevel.INFO) {
      const timestamp = new Date().toISOString();
      console.log(
        `%c[${timestamp}] [SUCCESS] ${context ? `[${context}]` : ''} ${message}`,
        this.styles.success,
        data || ''
      );
    }
  }

  warn(message: string, context?: string, data?: any): void {
    if (this.logLevel <= LogLevel.WARN) {
      const timestamp = new Date().toISOString();
      console.warn(
        `%c[${timestamp}] [WARN] ${context ? `[${context}]` : ''} ${message}`,
        this.styles.warn,
        data || ''
      );
    }
  }

  error(message: string, context?: string, error?: any): void {
    if (this.logLevel <= LogLevel.ERROR) {
      const timestamp = new Date().toISOString();
      console.error(
        `%c[${timestamp}] [ERROR] ${context ? `[${context}]` : ''} ${message}`,
        this.styles.error,
        error || ''
      );

      if (error?.stack) {
        console.error('Stack trace:', error.stack);
      }
    }
  }

  apiRequest(method: string, url: string, payload?: any): void {
    this.debug(`API Request: ${method} ${url}`, 'HTTP', payload);
  }

  apiResponse(method: string, url: string, status: number, response?: any): void {
    if (status >= 200 && status < 300) {
      this.success(`API Response: ${method} ${url} - ${status}`, 'HTTP', response);
    } else {
      this.error(`API Response: ${method} ${url} - ${status}`, 'HTTP', response);
    }
  }

  apiError(method: string, url: string, error: any): void {
    this.error(
      `API Error: ${method} ${url} - ${error.status || 'Network Error'}`,
      'HTTP',
      {
        message: error.message,
        status: error.status,
        statusText: error.statusText,
        error: error.error
      }
    );
  }

  setLogLevel(level: LogLevel): void {
    this.logLevel = level;
    this.info(`Log level set to: ${LogLevel[level]}`, 'Logger');
  }
}
