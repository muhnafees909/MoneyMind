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

  onLogin() {
    if (this.isLoading) {
      return;
    }
    this.errorMessage = '';
    this.isLoading = true;

    this.authService.login(this.email, this.password).subscribe({
      next: () => {
        // Session cookies are set by the server; land where the user
        // was originally heading (or the dashboard)
        const target =
          this.returnUrl && this.returnUrl.startsWith('/') ? this.returnUrl : '/dashboard';
        this.router.navigateByUrl(target);
      },
      error: (error) => {
        this.isLoading = false;
        this.errorMessage =
          error.error?.message || error.error?.error || 'Those credentials did not match. Try again.';
      }
    });
  }
}
