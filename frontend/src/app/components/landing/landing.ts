import {
  AfterViewInit,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  ViewChild
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { animate, stagger } from 'motion';
import {
  LucideArrowRight,
  LucideCheck,
  LucideChevronDown,
  LucideLandmark,
  LucideMail,
  LucideMessageSquareText,
  LucideRefreshCw,
  LucideRepeat,
  LucideShieldCheck,
  LucideTriangleAlert
} from '@lucide/angular';
import { CountUpDirective } from '../../shared/count-up.directive';
import { WordmarkComponent } from '../../shared/wordmark.component';

// Payday waterfall demo figures (mirrors the envelope screen's real math)
const PAYDAY = {
  deposit: 2700,
  accountBase: 7483.62,
  accountAfter: 10183.62,
  envelopes: [
    { name: 'Emergency fund', color: '#6c9de6', base: 4200, after: 4700, target: 6000, rule: '$500 first' },
    { name: 'Japan trip', color: '#27b9de', base: 1850, after: 2525, target: 3500, rule: 'then 25%' }
  ],
  unallocatedBase: 1433.62,
  unallocatedAfter: 2958.62
};

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    CountUpDirective,
    LucideArrowRight,
    LucideCheck,
    LucideChevronDown,
    LucideLandmark,
    LucideMail,
    LucideMessageSquareText,
    LucideRefreshCw,
    LucideRepeat,
    LucideShieldCheck,
    LucideTriangleAlert,
    WordmarkComponent
  ],
  templateUrl: './landing.html',
  styleUrl: './landing.scss'
})
export class LandingComponent implements AfterViewInit, OnDestroy {
  @ViewChild('hero') hero?: ElementRef<HTMLElement>;
  @ViewChild('bloom') bloom?: ElementRef<HTMLElement>;

  readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ----- hero motif -----
  heroRevealed = false;
  heroBalance = 0;

  // ----- payday waterfall demo -----
  payday = PAYDAY;
  envBalances = PAYDAY.envelopes.map((e) => e.base);
  unallocated = PAYDAY.unallocatedBase;
  accountBalance = PAYDAY.accountBase;
  depositVisible = false;
  paydayRunning = false;
  paydayRan = false;

  // ----- recurring detection demo -----
  recStage = 0;

  // ----- advisor demo -----
  advStage = 0;
  typedQuestion = '';
  private readonly advisorQuestion = 'Can I afford the Japan trip by March?';

  private cleanups: Array<() => void> = [];
  private timeouts: Array<ReturnType<typeof setTimeout>> = [];
  private observer?: IntersectionObserver;

  constructor(
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {}

  ngAfterViewInit() {
    if (this.reducedMotion) {
      // Everything lands in its final state, no choreography
      this.heroRevealed = true;
      this.heroBalance = 12483.62;
      this.recStage = 4;
      this.advStage = 3;
      this.typedQuestion = this.advisorQuestion;
      return;
    }
    this.zone.runOutsideAngular(() => {
      this.runLoadSequence();
      this.setupScrollReveals();
      this.setupMagneticButtons();
      this.setupHeroBloom();
    });
  }

  ngOnDestroy() {
    this.cleanups.forEach((fn) => fn());
    this.timeouts.forEach((t) => clearTimeout(t));
    this.observer?.disconnect();
  }

  private later(fn: () => void, ms: number) {
    this.timeouts.push(setTimeout(fn, ms));
  }

  // ============================================
  // LOAD SEQUENCE — deliberate arrival order:
  // frame → eyebrow → headline lines (masked) → sub → CTAs → hero card → numbers
  // ============================================
  private runLoadSequence() {
    const root = this.host.nativeElement;
    const q = (sel: string) => root.querySelectorAll(sel);
    const ease = [0.22, 1, 0.36, 1] as [number, number, number, number];

    animate(q('.topbar'), { opacity: [0, 1], transform: ['translateY(-8px)', 'translateY(0)'] },
      { duration: 0.6, delay: 0.1, ease });
    animate(q('.hero-eyebrow'), { opacity: [0, 1] }, { duration: 0.5, delay: 0.3, ease });
    animate(q('.line-inner'), { transform: ['translateY(115%)', 'translateY(0)'] },
      { duration: 0.85, delay: stagger(0.11, { startDelay: 0.4 }), ease });
    animate(q('.hero-sub'), { opacity: [0, 1], transform: ['translateY(14px)', 'translateY(0)'] },
      { duration: 0.6, delay: 0.95, ease });
    animate(q('.hero-ctas'), { opacity: [0, 1], transform: ['translateY(14px)', 'translateY(0)'] },
      { duration: 0.6, delay: 1.1, ease });
    animate(q('.hero-trust'), { opacity: [0, 1] }, { duration: 0.6, delay: 1.25, ease });
    animate(q('.hero-card'),
      { opacity: [0, 1], transform: ['translateY(28px) scale(0.975)', 'translateY(0) scale(1)'] },
      { duration: 0.85, delay: 1.0, ease });
    animate(q('.scroll-hint'), { opacity: [0, 0.7] }, { duration: 0.8, delay: 1.9, ease });

    // The signature moment: the balance counts and the band inks in
    this.later(() => {
      this.zone.run(() => {
        this.heroRevealed = true;
        this.heroBalance = 12483.62;
      });
    }, 1450);
  }

  // ============================================
  // SCROLL REVEALS — one observer, per-section choreography;
  // demo sections start their sequence when they enter
  // ============================================
  private setupScrollReveals() {
    const sections = Array.from(
      this.host.nativeElement.querySelectorAll<HTMLElement>('[data-section]')
    );
    this.observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) {
            continue;
          }
          const el = entry.target as HTMLElement;
          this.observer?.unobserve(el);
          const reveals = el.querySelectorAll('[data-reveal]');
          if (reveals.length > 0) {
            animate(
              reveals,
              { opacity: [0, 1], transform: ['translateY(26px)', 'translateY(0)'] },
              { duration: 0.7, delay: stagger(0.09), ease: [0.22, 1, 0.36, 1] }
            );
          }
          const words = el.querySelectorAll('[data-word]');
          if (words.length > 0) {
            animate(
              words,
              { opacity: [0, 1], transform: ['translateY(0.35em)', 'translateY(0)'] },
              { duration: 0.6, delay: stagger(0.07), ease: [0.22, 1, 0.36, 1] }
            );
          }
          const demo = el.dataset['demo'];
          if (demo) {
            this.zone.run(() => this.startDemo(demo));
          }
        }
      },
      { threshold: 0.3 }
    );
    sections.forEach((s) => this.observer?.observe(s));
  }

  private startDemo(name: string) {
    if (name === 'payday' && !this.paydayRan) {
      this.later(() => this.zone.run(() => this.runPayday()), 500);
    }
    if (name === 'recurring' && this.recStage === 0) {
      this.runRecurring();
    }
    if (name === 'advisor' && this.advStage === 0) {
      this.runAdvisor();
    }
  }

  // ============================================
  // DEMO A — payday waterfall (replayable)
  // ============================================
  runPayday() {
    if (this.paydayRunning) {
      return;
    }
    this.paydayRunning = true;
    this.paydayRan = true;
    this.depositVisible = false;
    this.envBalances = this.payday.envelopes.map((e) => e.base);
    this.unallocated = this.payday.unallocatedBase;
    this.accountBalance = this.payday.accountBase;

    this.later(() => this.zone.run(() => {
      this.depositVisible = true;
      this.accountBalance = this.payday.accountAfter;
    }), 350);
    this.later(() => this.zone.run(() => {
      this.envBalances = [this.payday.envelopes[0].after, this.envBalances[1]];
    }), 1250);
    this.later(() => this.zone.run(() => {
      this.envBalances = [this.envBalances[0], this.payday.envelopes[1].after];
    }), 2050);
    this.later(() => this.zone.run(() => {
      this.unallocated = this.payday.unallocatedAfter;
      this.paydayRunning = false;
    }), 2850);
  }

  bandWidth(value: number): number {
    return (value / this.payday.accountAfter) * 100;
  }

  // ============================================
  // DEMO B — recurring detection sequence (replayable)
  // ============================================
  runRecurring() {
    this.recStage = 1;
    this.later(() => this.zone.run(() => (this.recStage = 2)), 1300);
    this.later(() => this.zone.run(() => (this.recStage = 3)), 2100);
    this.later(() => this.zone.run(() => (this.recStage = 4)), 2900);
  }

  replayRecurring() {
    this.recStage = 0;
    this.later(() => this.zone.run(() => this.runRecurring()), 80);
  }

  // ============================================
  // DEMO C — advisor Q&A: typed question → thinking rule → grounded answer
  // ============================================
  runAdvisor() {
    this.advStage = 1;
    this.typedQuestion = '';
    let i = 0;
    const type = () => {
      if (i < this.advisorQuestion.length) {
        this.typedQuestion += this.advisorQuestion[i++];
        this.timeouts.push(setTimeout(() => this.zone.run(type), 26));
      } else {
        this.later(() => this.zone.run(() => (this.advStage = 2)), 250);
        this.later(() => this.zone.run(() => (this.advStage = 3)), 1600);
      }
    };
    type();
  }

  replayAdvisor() {
    this.advStage = 0;
    this.later(() => this.zone.run(() => this.runAdvisor()), 80);
  }

  // ============================================
  // MAGNETIC CTAS — the primary buttons lean toward the cursor
  // ============================================
  private setupMagneticButtons() {
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
      return;
    }
    const buttons = Array.from(
      this.host.nativeElement.querySelectorAll<HTMLElement>('.magnetic')
    );
    for (const btn of buttons) {
      const onMove = (e: PointerEvent) => {
        const box = btn.getBoundingClientRect();
        const dx = e.clientX - (box.left + box.width / 2);
        const dy = e.clientY - (box.top + box.height / 2);
        btn.style.transition = 'transform 0.08s linear';
        btn.style.transform = `translate(${dx * 0.22}px, ${dy * 0.22}px)`;
      };
      const onLeave = () => {
        btn.style.transition = 'transform 0.45s cubic-bezier(0.34, 1.56, 0.64, 1)';
        btn.style.transform = 'translate(0, 0)';
      };
      btn.addEventListener('pointermove', onMove);
      btn.addEventListener('pointerleave', onLeave);
      this.cleanups.push(() => {
        btn.removeEventListener('pointermove', onMove);
        btn.removeEventListener('pointerleave', onLeave);
      });
    }
  }

  // ============================================
  // HERO BLOOM — the fern light trails the cursor across the hero
  // ============================================
  private setupHeroBloom() {
    const hero = this.hero?.nativeElement;
    const bloom = this.bloom?.nativeElement;
    if (!hero || !bloom || !window.matchMedia('(hover: hover)').matches) {
      return;
    }
    let targetX = hero.clientWidth * 0.3;
    let targetY = hero.clientHeight * 0.3;
    let x = targetX;
    let y = targetY;
    let raf = 0;
    const tick = () => {
      x += (targetX - x) * 0.07;
      y += (targetY - y) * 0.07;
      bloom.style.transform = `translate(${x - 320}px, ${y - 320}px)`;
      raf = requestAnimationFrame(tick);
    };
    const onMove = (e: PointerEvent) => {
      const box = hero.getBoundingClientRect();
      targetX = e.clientX - box.left;
      targetY = e.clientY - box.top;
    };
    hero.addEventListener('pointermove', onMove);
    raf = requestAnimationFrame(tick);
    this.cleanups.push(() => {
      hero.removeEventListener('pointermove', onMove);
      cancelAnimationFrame(raf);
    });
  }
}
