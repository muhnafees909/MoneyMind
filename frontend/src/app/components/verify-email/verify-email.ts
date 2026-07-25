import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { LucideCircleCheck, LucideOctagonAlert, LucideLoader } from '@lucide/angular';
import { AuthService } from '../../services/auth.service';
import { WordmarkComponent } from '../../shared/wordmark.component';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    LucideCircleCheck,
    LucideOctagonAlert,
    LucideLoader,
    WordmarkComponent
  ],
  templateUrl: './verify-email.html',
  styleUrl: './verify-email.scss'
})
export class VerifyEmailComponent implements OnInit {
  state = signal<'verifying' | 'success' | 'error'>('verifying');
  message = signal('');
  loggedIn = false;

  constructor(
    private route: ActivatedRoute,
    private authService: AuthService
  ) {}

  ngOnInit() {
    this.loggedIn = this.authService.isLoggedIn();
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.state.set('error');
      this.message.set('This verification link is missing its token.');
      return;
    }
    this.authService.verifyEmail(token).subscribe({
      next: () => {
        this.state.set('success');
        // Refresh cached user so the banner/gating clear immediately
        if (this.loggedIn) {
          this.authService.loadCurrentUser().subscribe({ error: () => {} });
        }
      },
      error: (err) => {
        this.state.set('error');
        this.message.set(err.error?.message || 'This verification link is invalid or expired.');
      }
    });
  }
}
