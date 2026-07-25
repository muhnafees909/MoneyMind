import { Component, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LucideMailWarning, LucideX } from '@lucide/angular';
import { AuthService } from '../../services/auth.service';

/**
 * App-wide nudge shown to signed-in users whose email isn't verified yet.
 * Non-blocking (basic access is allowed); only bank linking is gated.
 */
@Component({
  selector: 'app-verification-banner',
  standalone: true,
  imports: [CommonModule, LucideMailWarning, LucideX],
  templateUrl: './verification-banner.html',
  styleUrl: './verification-banner.scss'
})
export class VerificationBannerComponent {
  dismissed = signal(false);
  resent = signal(false);
  sending = signal(false);
  error = signal('');

  readonly show = computed(() => {
    const u = this.auth.currentUser();
    return !!u && !u.email_verified && !this.dismissed();
  });

  constructor(private auth: AuthService) {}

  resend() {
    if (this.sending()) {
      return;
    }
    this.sending.set(true);
    this.error.set('');
    this.auth.resendVerification().subscribe({
      next: () => {
        this.sending.set(false);
        this.resent.set(true);
      },
      error: (err) => {
        this.sending.set(false);
        this.error.set(err.error?.message || 'Could not send right now — try again shortly.');
      }
    });
  }

  dismiss() {
    this.dismissed.set(true);
  }
}
