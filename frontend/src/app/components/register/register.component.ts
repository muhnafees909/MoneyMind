import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './register.component.html',
  styleUrls: ['./register.component.scss'],
})
export class RegisterComponent {
  firstName: string = '';
  lastName: string = '';
  email: string = '';
  password: string = '';
  confirmPassword: string = '';
  agreeToTerms: boolean = false;
  errorMessage: string = '';
  successMessage: string = '';
  isLoading: boolean = false;

  showPassword: boolean = false;
  showConfirmPassword: boolean = false;

  constructor(
    private authService: AuthService,
    private router: Router
  ) {}

  togglePasswordVisibility(): void {
    this.showPassword = !this.showPassword;
  }

  toggleConfirmPasswordVisibility(): void {
    this.showConfirmPassword = !this.showConfirmPassword;
  }

  validateForm(): boolean {
    this.errorMessage = '';

    // Check required fields
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

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(this.email)) {
      this.errorMessage = 'Please enter a valid email address';
      return false;
    }

    if (!this.password) {
      this.errorMessage = 'Password is required';
      return false;
    }

    // Validate password strength (at least 8 characters)
    if (this.password.length < 8) {
      this.errorMessage = 'Password must be at least 8 characters long';
      return false;
    }

    if (!this.confirmPassword) {
      this.errorMessage = 'Please confirm your password';
      return false;
    }

    if (this.password !== this.confirmPassword) {
      this.errorMessage = 'Passwords do not match';
      return false;
    }

    if (!this.agreeToTerms) {
      this.errorMessage = 'You must agree to the Terms & Conditions';
      return false;
    }

    return true;
  }

  onRegister(): void {
    if (!this.validateForm()) {
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    const registrationData = {
      first_name: this.firstName.trim(),
      last_name: this.lastName.trim(),
      email: this.email.trim(),
      password: this.password,
    };

    this.authService.register(registrationData).subscribe({
      next: (response) => {
        this.successMessage = 'Account created successfully! Redirecting...';
        this.authService.saveToken(response.access_token);
        setTimeout(() => {
          this.router.navigate(['/dashboard']);
        }, 1500);
      },
      error: (error) => {
        this.isLoading = false;
        this.errorMessage = error.error?.message || 'Registration failed. Please try again.';
        console.error('Registration error:', error);
      },
    });
  }
}
