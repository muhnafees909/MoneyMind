import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import {
  LucideArrowRight,
  LucideCircleCheck,
  LucideEye,
  LucideEyeOff,
  LucideOctagonAlert,
  LucideShieldCheck,
  LucideTarget,
  LucideTrendingUp
} from '@lucide/angular';
import { AuthService } from '../../services/auth.service';
import { ModalService } from '../../services/modal.service';
import { WordmarkComponent } from '../../shared/wordmark.component';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    LucideArrowRight,
    LucideCircleCheck,
    LucideEye,
    LucideEyeOff,
    LucideOctagonAlert,
    LucideShieldCheck,
    LucideTarget,
    LucideTrendingUp,
    WordmarkComponent
  ],
  templateUrl: './register.component.html',
  styleUrls: ['./register.component.scss']
})
export class RegisterComponent {
  firstName = '';
  lastName = '';
  email = '';
  password = '';
  confirmPassword = '';
  agreeToTerms = false;
  errorMessage = '';
  successMessage = '';
  isLoading = false;

  showPassword = false;
  showConfirmPassword = false;

  constructor(
    private authService: AuthService,
    private router: Router,
    private modalService: ModalService
  ) {}

  /** Open Terms/Privacy as a modal without navigating away — signup form state
   *  underneath is preserved. */
  openLegal(section: 'terms' | 'privacy', event: Event): void {
    // preventDefault stops both the anchor navigation and the wrapping <label>
    // from toggling the "agree" checkbox; stopPropagation is belt-and-suspenders.
    event.preventDefault();
    event.stopPropagation();
    this.modalService.showLegal(section);
  }

  togglePasswordVisibility(): void {
    this.showPassword = !this.showPassword;
  }

  toggleConfirmPasswordVisibility(): void {
    this.showConfirmPassword = !this.showConfirmPassword;
  }

  validateForm(): boolean {
    this.errorMessage = '';

    if (!this.firstName.trim()) {
      this.errorMessage = 'First name is required';
      return false;
    }
    if (!this.lastName.trim()) {
      this.errorMessage = 'Last name is required';
      return false;
    }
    if (!this.email.trim()) {
      this.errorMessage = 'Email is required';
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(this.email)) {
      this.errorMessage = 'Please enter a valid email address';
      return false;
    }
    if (!this.password) {
      this.errorMessage = 'Password is required';
      return false;
    }
    if (this.password.length < 8) {
      this.errorMessage = 'Password must be at least 8 characters';
      return false;
    }
    if (!this.confirmPassword) {
      this.errorMessage = 'Please confirm your password';
      return false;
    }
    if (this.password !== this.confirmPassword) {
      this.errorMessage = 'Those passwords do not match';
      return false;
    }
    if (!this.agreeToTerms) {
      this.errorMessage = 'Please accept the Terms to continue';
      return false;
    }
    return true;
  }

  onRegister(): void {
    if (this.isLoading || !this.validateForm()) {
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    const registrationData = {
      first_name: this.firstName.trim(),
      last_name: this.lastName.trim(),
      email: this.email.trim(),
      password: this.password
    };

    this.authService.register(registrationData).subscribe({
      next: () => {
        // Session cookies are set by the server on register
        this.successMessage = 'Account created — taking you in…';
        // New accounts get the optional setup flow first (skippable)
        setTimeout(() => this.router.navigate(['/welcome']), 1200);
      },
      error: (error) => {
        this.isLoading = false;
        this.errorMessage = error.error?.message || error.error?.error || 'Could not create your account. Try again.';
      }
    });
  }
}
