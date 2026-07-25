import {
  HttpBackend,
  HttpClient,
  HttpErrorResponse,
  HttpHeaders,
  HttpInterceptorFn,
  HttpRequest
} from '@angular/common/http';
import { inject } from '@angular/core';
import { Observable, catchError, finalize, shareReplay, switchMap, tap, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { SessionService } from '../services/session.service';

// One refresh at a time: parallel 401s all wait on the same attempt
let refreshInFlight: Observable<unknown> | null = null;

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Prepare an API request for cookie auth:
 * - send credentials (the httpOnly session cookies)
 * - strip any legacy Authorization header (cookies are canonical)
 * - attach the CSRF double-submit header on state-changing methods
 */
function isApiRequest(url: string): boolean {
  // Dev: absolute apiUrl (http://localhost:5000/api/...).
  // Prod: apiUrl is '' and API calls are same-origin relative (/api/...).
  return environment.apiUrl
    ? url.startsWith(`${environment.apiUrl}/api/`)
    : url.startsWith('/api/');
}

function prepare(req: HttpRequest<unknown>): HttpRequest<unknown> {
  if (!isApiRequest(req.url)) {
    return req;
  }
  let headers = req.headers.delete('Authorization');
  const mutating = !['GET', 'HEAD', 'OPTIONS'].includes(req.method);
  if (mutating) {
    const csrf = readCookie(
      req.url.includes('/api/auth/refresh') ? 'csrf_refresh_token' : 'csrf_access_token'
    );
    if (csrf) {
      headers = headers.set('X-CSRF-TOKEN', csrf);
    }
  }
  return req.clone({ headers, withCredentials: true });
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const session = inject(SessionService);
  // Raw client (bypasses interceptors) for the refresh call itself
  const rawHttp = new HttpClient(inject(HttpBackend));

  const prepared = prepare(req);
  if (!prepared.withCredentials) {
    return next(prepared); // non-API traffic (fonts, etc.)
  }

  const isAuthEndpoint = /\/api\/auth\/(login|register|refresh|logout)/.test(req.url);

  return next(prepared).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status !== 401 || isAuthEndpoint) {
        return throwError(() => error);
      }

      // Access cookie rejected — try one refresh, then retry the request
      if (!refreshInFlight) {
        const csrf = readCookie('csrf_refresh_token');
        refreshInFlight = rawHttp
          .post(
            `${environment.apiUrl}/api/auth/refresh`,
            {},
            {
              withCredentials: true,
              headers: csrf ? new HttpHeaders({ 'X-CSRF-TOKEN': csrf }) : undefined
            }
          )
          .pipe(
            // A successful refresh resets the idle-timeout clock too
            tap(() => session.extend()),
            shareReplay(1),
            finalize(() => (refreshInFlight = null))
          );
      }

      return refreshInFlight.pipe(
        switchMap(() => next(prepare(req))), // re-prepare: fresh CSRF cookie
        catchError((refreshError) => {
          // Refresh failed → the session is genuinely over. Route through the
          // SessionService so the timer/modal reset and we redirect with the
          // "expired" notice, preserving the current page as returnUrl.
          session.expire();
          return throwError(() => refreshError);
        })
      );
    })
  );
};
