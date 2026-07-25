import { Injectable, NgZone, signal } from '@angular/core';
import { HttpBackend, HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

// The access token lives 30 minutes (backend: JWT_ACCESS_TOKEN_EXPIRES).
// That's the session that lapses when a tab is left idle; the 12h refresh
// token backs the "Continue" extension.
const ACCESS_TOKEN_MS = 30 * 60 * 1000;
// Warn this long before the access token expires.
const WARN_MS = 60 * 1000;
// If the user interacted within this window as expiry nears, refresh silently
// instead of nagging — only a genuinely idle tab should see the warning.
const ACTIVITY_RECENT_MS = 60 * 1000;
// When the timer resumes on reload, this is the localStorage key holding the
// current access token's expiry (epoch ms). SessionService owns it entirely.
const EXPIRES_KEY = 'mm_session_expires';

const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'mousemove', 'scroll', 'touchstart'];

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Watches the (idle) lifetime of the session and drives the timeout warning.
 * - Ticks once a second; when the access token is ~60s from expiring it either
 *   silently refreshes (if the user is active) or shows the warning modal.
 * - "Continue" refreshes and resets the clock; "Log out" / countdown-to-zero
 *   ends the session and redirects to login.
 * The already-expired path (a 401 with no valid refresh) is handled by the auth
 * interceptor, which calls expire() here so the timer and modal reset too.
 */
@Injectable({ providedIn: 'root' })
export class SessionService {
  // Signals consumed by the timeout modal
  readonly warningVisible = signal(false);
  readonly secondsLeft = signal(Math.floor(WARN_MS / 1000));
  readonly continuing = signal(false);

  private ticker: ReturnType<typeof setInterval> | null = null;
  private lastActivityAt = Date.now();
  // Ensures the activity-based silent refresh is attempted at most once per
  // warning window — if it fails, we fall back to the visible warning.
  private silentRefreshTried = false;
  // Plain (non-signal) in-flight guard for the silent refresh — it runs from
  // the out-of-zone ticker, so it must NOT touch view-bound signals.
  private refreshing = false;
  private rawHttp: HttpClient;
  private readonly onActivity = () => {
    this.lastActivityAt = Date.now();
  };

  constructor(
    private auth: AuthService,
    private router: Router,
    private zone: NgZone,
    httpBackend: HttpBackend
  ) {
    // Raw client bypasses the auth interceptor for the refresh call itself
    this.rawHttp = new HttpClient(httpBackend);
    // Start/stop the timer as the signed-in state changes (login, logout,
    // reload while authenticated).
    this.auth.authState$.subscribe((loggedIn) => (loggedIn ? this.start() : this.stop()));
  }

  // ----- lifecycle -----

  private start() {
    // Resume the real expiry on reload; otherwise this is a fresh session.
    const stored = Number(localStorage.getItem(EXPIRES_KEY));
    if (!stored || stored <= Date.now()) {
      this.setExpiry(Date.now() + ACCESS_TOKEN_MS);
    }
    this.lastActivityAt = Date.now();
    this.silentRefreshTried = false;
    this.refreshing = false;
    ACTIVITY_EVENTS.forEach((e) =>
      document.addEventListener(e, this.onActivity, { passive: true })
    );
    if (!this.ticker) {
      // Outside Angular so a 1s heartbeat doesn't trigger app-wide change
      // detection; we re-enter the zone only when the modal state changes.
      this.zone.runOutsideAngular(() => {
        this.ticker = setInterval(() => this.tick(), 1000);
      });
    }
  }

  private stop() {
    if (this.ticker) {
      clearInterval(this.ticker);
      this.ticker = null;
    }
    ACTIVITY_EVENTS.forEach((e) => document.removeEventListener(e, this.onActivity));
    localStorage.removeItem(EXPIRES_KEY);
    if (this.warningVisible()) {
      this.zone.run(() => this.warningVisible.set(false));
    } else {
      this.warningVisible.set(false);
    }
  }

  private setExpiry(at: number) {
    localStorage.setItem(EXPIRES_KEY, String(at));
  }

  private get expiresAt(): number {
    return Number(localStorage.getItem(EXPIRES_KEY)) || 0;
  }

  /** Reset the clock to a full session (after any successful token refresh). */
  extend() {
    this.setExpiry(Date.now() + ACCESS_TOKEN_MS);
    this.silentRefreshTried = false;
    this.refreshing = false;
    // Run inside the zone: the ticker fires these from outside Angular, and the
    // modal's visibility/button state must re-render.
    this.zone.run(() => {
      this.warningVisible.set(false);
      this.continuing.set(false);
    });
  }

  // ----- the heartbeat -----

  private tick() {
    if (!this.auth.isLoggedIn()) {
      this.stop();
      return;
    }
    const remaining = this.expiresAt - Date.now();

    if (remaining <= 0) {
      this.zone.run(() => this.expire());
      return;
    }

    if (remaining <= WARN_MS) {
      const recentlyActive = Date.now() - this.lastActivityAt <= ACTIVITY_RECENT_MS;
      if (recentlyActive && !this.silentRefreshTried && !this.refreshing) {
        // Active user about to lapse — try once to keep them in silently.
        this.silentRefresh();
        return;
      }
      // Idle tab (or silent refresh failed): surface the warning + countdown.
      this.zone.run(() => {
        this.warningVisible.set(true);
        this.secondsLeft.set(Math.ceil(remaining / 1000));
      });
    } else if (this.warningVisible()) {
      this.zone.run(() => this.warningVisible.set(false));
    }
  }

  // ----- user / auto actions -----

  /** "Continue" button — extend the session and dismiss the modal. Invoked
   * from a click handler, so it already runs inside the Angular zone. */
  continueSession() {
    if (this.continuing()) {
      return;
    }
    this.continuing.set(true);
    this.refresh().subscribe({
      next: () => this.extend(),
      error: () => this.zone.run(() => this.expire())
    });
  }

  private silentRefresh() {
    this.silentRefreshTried = true; // attempt only once per window
    this.refreshing = true; // plain guard — no view binding, safe out of zone
    this.refresh().subscribe({
      next: () => this.extend(),
      // Refresh token also gone → show the warning (countdown → expire)
      error: () => (this.refreshing = false)
    });
  }

  private refresh() {
    const csrf = readCookie('csrf_refresh_token');
    return this.rawHttp.post(
      `${environment.apiUrl}/api/auth/refresh`,
      {},
      {
        withCredentials: true,
        headers: csrf ? new HttpHeaders({ 'X-CSRF-TOKEN': csrf }) : undefined
      }
    );
  }

  /** "Log out" button — deliberate sign-out. */
  logoutNow() {
    this.warningVisible.set(false);
    this.auth.logout(); // clears session (→ stop()) and tells the server
    this.router.navigate(['/login']);
  }

  /**
   * Session ran out (countdown hit zero, or a 401 with no valid refresh).
   * Clear local auth, preserve where the user was, and bounce to login with
   * the "expired" notice. Called from tick() and from the auth interceptor.
   */
  expire() {
    if (!this.auth.isLoggedIn()) {
      return; // already handled
    }
    const returnUrl = this.router.url;
    this.warningVisible.set(false);
    this.auth.clearSession(); // local only (→ stop()); cookies are already dead
    this.router.navigate(['/login'], {
      queryParams: { expired: '1', returnUrl }
    });
  }
}
