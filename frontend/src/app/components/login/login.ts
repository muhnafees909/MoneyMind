import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import {
  LucideArrowRight,
  LucideEye,
  LucideEyeOff,
  LucideOctagonAlert,
  LucideShieldCheck,
  LucideTarget,
  LucideTrendingUp,
  LucideTriangleAlert
} from '@lucide/angular';
import { AuthService } from '../../services/auth.service';
import { WordmarkComponent } from '../../shared/wordmark.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    LucideArrowRight,
    LucideEye,
    LucideEyeOff,
    LucideOctagonAlert,
    LucideShieldCheck,
    LucideTarget,
    LucideTrendingUp,
    LucideTriangleAlert,
    WordmarkComponent
  ],
  templateUrl: './login.html',
  styleUrl: './login.scss'
})
export class Login implements OnInit {
  email = '';
  password = '';
  errorMessage = '';
  sessionNotice = '';
  showPassword = false;
  isLoading = false;

  // MFA second step
  mfaStep = false;
  mfaCode = '';
  private mfaToken = '';

  private returnUrl: string | null = null;

  constructor(
    private authService: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {}

  ngOnInit() {
    const params = this.route.snapshot.queryParamMap;
    this.returnUrl = params.get('returnUrl');
    if (params.get('expired') === '1') {
      this.sessionNotice = 'Your session expired — please sign in again.';
    }
  }

  togglePasswordVisibility() {
    this.showPassword = !this.showPassword;
  }

  private goToApp() {
    const target =
      this.returnUrl && this.returnUrl.startsWith('/') ? this.returnUrl : '/dashboard';
    this.router.navigateByUrl(target);
  }

  onLogin() {
    if (this.isLoading) {
      return;
    }
    this.errorMessage = '';
    this.sessionNotice = '';
    this.isLoading = true;

    this.authService.login(this.email, this.password).subscribe({
      next: (res) => {
        if (res.mfa_required && res.mfa_token) {
          // Password accepted; ask for the authenticator code before any session.
          this.mfaToken = res.mfa_token;
          this.mfaStep = true;
          this.isLoading = false;
          return;
        }
        this.goToApp();
      },
      error: (error) => {
        this.isLoading = false;
        // Distinct lockout message (429) vs. non-revealing credential error.
        this.errorMessage =
          error.error?.message || 'Those credentials did not match. Try again.';
      }
    });
  }

  onVerifyMfa() {
    if (this.isLoading || !this.mfaCode.trim()) {
      return;
    }
    this.errorMessage = '';
    this.isLoading = true;
    this.authService.completeMfaLogin(this.mfaToken, this.mfaCode.trim()).subscribe({
      next: () => this.goToApp(),
      error: (error) => {
        this.isLoading = false;
        this.errorMessage = error.error?.message || 'That code isn’t right. Try again.';
        if (error.error?.code === 'mfa_expired') {
          // Pending token lapsed — send them back to the password step.
          this.mfaStep = false;
          this.mfaCode = '';
        }
      }
    });
  }

  backToPassword() {
    this.mfaStep = false;
    this.mfaCode = '';
    this.errorMessage = '';
  }
}
