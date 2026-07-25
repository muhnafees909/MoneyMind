import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { Navigation } from './components/navigation/navigation';
import { SessionTimeoutComponent } from './components/session-timeout/session-timeout';
import { VerificationBannerComponent } from './components/verification-banner/verification-banner';
import { SessionService } from './services/session.service';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Navigation, SessionTimeoutComponent, VerificationBannerComponent],
  template: `
    <app-navigation></app-navigation>
    <app-verification-banner></app-verification-banner>
    <router-outlet></router-outlet>
    <app-session-timeout></app-session-timeout>
  `,
  styles: []
})
export class App implements OnInit {
  title = 'MoneyMind';

  // Injecting SessionService here guarantees the idle timer is running from
  // app start (it self-starts/stops from the auth state).
  constructor(
    private session: SessionService,
    private auth: AuthService
  ) {}

  ngOnInit() {
    // Load verification/MFA state so the banner + gating reflect reality on
    // a fresh page load (when the session cookie is already present).
    if (this.auth.isLoggedIn()) {
      this.auth.loadCurrentUser().subscribe({ error: () => {} });
    }
  }
}
