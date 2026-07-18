import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import {
  LucideArrowLeft,
  LucideArrowRight,
  LucideBriefcase,
  LucideCircleCheck,
  LucideHouse,
  LucideUsers
} from '@lucide/angular';
import { AdvisorProfile, ProfileService } from '../../services/profile.service';
import { WordmarkComponent } from '../../shared/wordmark.component';

/**
 * Optional post-signup wizard. Writes to the same user_profile model as the
 * Profile screen; entirely skippable at every step — skipping never blocks
 * the app, and anything already answered is quietly kept.
 */
@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    LucideArrowLeft,
    LucideArrowRight,
    LucideBriefcase,
    LucideCircleCheck,
    LucideHouse,
    LucideUsers,
    WordmarkComponent
  ],
  templateUrl: './onboarding.html',
  styleUrl: './onboarding.scss'
})
export class OnboardingComponent {
  step = 1; // 1..3 questions, 4 = completion
  readonly totalSteps = 3;
  direction: 'forward' | 'back' = 'forward';
  saving = false;

  form = {
    employment_status: '' as string,
    annual_income: null as number | null,
    marital_status: '' as string,
    dependents: null as number | null,
    housing_status: '' as string,
    birth_year: null as number | null
  };

  readonly maxBirthYear = new Date().getFullYear() - 13;

  constructor(
    private profileService: ProfileService,
    private router: Router
  ) {}

  progressPct(): number {
    return (Math.min(this.step, this.totalSteps) / this.totalSteps) * 100;
  }

  next() {
    if (this.step < this.totalSteps) {
      this.direction = 'forward';
      this.step++;
      return;
    }
    // Finishing step 3: persist, then show the quiet completion
    this.persist(() => {
      this.direction = 'forward';
      this.step = 4;
    });
  }

  back() {
    if (this.step > 1) {
      this.direction = 'back';
      this.step--;
    }
  }

  /** Skip the rest of the flow. Anything already answered is kept quietly. */
  skip() {
    if (this.hasAnyAnswer()) {
      this.persist(() => this.router.navigate(['/dashboard']));
    } else {
      this.router.navigate(['/dashboard']);
    }
  }

  finish() {
    this.router.navigate(['/dashboard']);
  }

  answeredCount(): number {
    return [
      this.form.employment_status,
      this.form.annual_income,
      this.form.marital_status,
      this.form.dependents,
      this.form.housing_status,
      this.form.birth_year
    ].filter((v) => v !== '' && v !== null && v !== undefined).length;
  }

  private hasAnyAnswer(): boolean {
    return this.answeredCount() > 0;
  }

  private persist(onDone: () => void) {
    if (this.saving) {
      return;
    }
    this.saving = true;
    this.profileService
      .updateProfile({
        employment_status: (this.form.employment_status || null) as AdvisorProfile['employment_status'],
        annual_income: this.form.annual_income,
        marital_status: (this.form.marital_status || null) as AdvisorProfile['marital_status'],
        dependents: this.form.dependents,
        housing_status: (this.form.housing_status || null) as AdvisorProfile['housing_status'],
        birth_year: this.form.birth_year
      })
      .subscribe({
        next: () => {
          this.saving = false;
          onDone();
        },
        error: () => {
          this.saving = false;
          // Setup must never trap the user: if saving fails, go straight to
          // the app (no false "you're set" screen) — everything here can be
          // entered later from Profile.
          this.router.navigate(['/dashboard']);
        }
      });
  }
}
