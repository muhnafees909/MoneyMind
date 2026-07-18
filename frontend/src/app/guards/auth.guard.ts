import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * UI-level gate for protected screens. This is a fast local check (the
 * real enforcement is the backend's cookie auth on every request); if the
 * hint is stale, the first API call 401s and the interceptor redirects
 * with the "session expired" message.
 */
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isLoggedIn()) {
    return true;
  }

  // Preserve where the user was heading so login can return them there
  return router.createUrlTree(['/login'], {
    queryParams: { returnUrl: state.url }
  });
};
