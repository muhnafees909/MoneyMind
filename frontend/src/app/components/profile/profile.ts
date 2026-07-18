import { Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { animate, stagger } from 'motion';
import {
  LucideBriefcase,
  LucideCheck,
  LucideCircleCheck,
  LucideHouse,
  LucideShieldCheck
} from '@lucide/angular';
import { AdvisorProfile, ProfileService } from '../../services/profile.service';
import { ModalService } from '../../services/modal.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    LucideBriefcase,
    LucideCheck,
    LucideCircleCheck,
    LucideHouse,
    LucideShieldCheck
  ],
  templateUrl: './profile.html',
  styleUrl: './profile.scss'
})
export class ProfileComponent implements OnInit {
  // Form state lives only here while the screen is open — nothing is cached
  form = {
    employment_status: '' as string,
    annual_income: null as number | null,
    marital_status: '' as string,
    dependents: null as number | null,
    housing_status: '' as string,
    birth_year: null as number | null
  };
  updatedAt: string | null = null;

  initialLoading = true;
  saving = false;
  toastVisible = false;
  preAnim = true;
  private entranceDone = false;
  private toastTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  readonly maxBirthYear = new Date().getFullYear() - 13;

  constructor(
    private profileService: ProfileService,
    private modalService: ModalService,
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {
    if (this.reducedMotion) {
      this.preAnim = false;
    }
  }

  ngOnInit() {
    this.profileService.getProfile().subscribe({
      next: (profile) => {
        this.applyProfile(profile);
        this.finishLoad();
      },
      error: () => {
        this.modalService.showError('Could not load your profile. Try again shortly.');
        this.finishLoad();
      }
    });
  }

  private applyProfile(profile: AdvisorProfile) {
    this.form = {
      employment_status: profile.employment_status || '',
      annual_income: profile.annual_income,
      marital_status: profile.marital_status || '',
      dependents: profile.dependents,
      housing_status: profile.housing_status || '',
      birth_year: profile.birth_year
    };
    this.updatedAt = profile.updated_at;
  }

  private finishLoad() {
    this.initialLoading = false;
    setTimeout(() => this.runEntrance(), 40);
  }

  save() {
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
        next: (profile) => {
          this.saving = false;
          this.applyProfile(profile);
          this.showToast();
        },
        error: (error) => {
          this.saving = false;
          this.modalService.showError(error?.error?.error || 'Could not save your profile');
        }
      });
  }

  private showToast() {
    this.toastVisible = true;
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
    }
    this.toastTimer = setTimeout(() => {
      this.zone.run(() => (this.toastVisible = false));
    }, 2400);
  }

  private runEntrance() {
    if (this.entranceDone) {
      return;
    }
    this.entranceDone = true;
    if (this.reducedMotion) {
      this.preAnim = false;
      return;
    }
    setTimeout(() => {
      const els = this.host.nativeElement.querySelectorAll('[data-animate]');
      this.preAnim = false;
      if (els.length === 0) {
        return;
      }
      this.zone.runOutsideAngular(() => {
        animate(
          els,
          { opacity: [0, 1], transform: ['translateY(10px)', 'translateY(0px)'] },
          { duration: 0.5, delay: stagger(0.06), ease: [0.22, 1, 0.36, 1] }
        );
      });
    });
  }
}
