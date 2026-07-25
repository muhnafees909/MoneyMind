import {
  AfterViewInit,
  Component,
  ElementRef,
  HostListener,
  ViewChild
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavigationEnd, Router, RouterModule } from '@angular/router';
import { filter } from 'rxjs/operators';
import {
  LucideLandmark,
  LucideTags,
  LucideLayoutDashboard,
  LucideLogOut,
  LucideMail,
  LucideMenu,
  LucideMessageSquareText,
  LucideReceiptText,
  LucideRepeat,
  LucideUserRound,
  LucideWallet,
  LucideX
} from '@lucide/angular';
import { AuthService } from '../../services/auth.service';
import { WordmarkComponent } from '../../shared/wordmark.component';

interface NavItem {
  path: string;
  label: string;
  icon: 'dashboard' | 'receipt' | 'wallet' | 'mail' | 'repeat' | 'chat';
}

@Component({
  selector: 'app-navigation',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    LucideLandmark,
    LucideTags,
    LucideLayoutDashboard,
    LucideLogOut,
    LucideMail,
    LucideMenu,
    LucideMessageSquareText,
    LucideReceiptText,
    LucideRepeat,
    LucideUserRound,
    LucideWallet,
    LucideX,
    WordmarkComponent
  ],
  templateUrl: './navigation.html',
  styleUrl: './navigation.scss'
})
export class Navigation implements AfterViewInit {
  @ViewChild('linksRail') linksRail?: ElementRef<HTMLElement>;

  readonly navItems: NavItem[] = [
    { path: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
    { path: '/transactions', label: 'Transactions', icon: 'receipt' },
    { path: '/budgets', label: 'Budgets', icon: 'wallet' },
    { path: '/envelopes', label: 'Goals & Envelopes', icon: 'mail' },
    { path: '/recurring', label: 'Recurring', icon: 'repeat' },
    { path: '/chat', label: 'Advisor', icon: 'chat' }
  ];

  mobileMenuOpen = false;

  // The sliding fern rule under the active item
  indicatorLeft = 0;
  indicatorWidth = 0;
  indicatorReady = false;

  constructor(
    private authService: AuthService,
    private router: Router
  ) {
    this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => {
        this.mobileMenuOpen = false;
        // routerLinkActive classes apply after change detection settles
        setTimeout(() => this.positionIndicator(), 60);
      });
  }

  ngAfterViewInit() {
    setTimeout(() => this.positionIndicator(), 60);
  }

  @HostListener('window:resize')
  onResize() {
    this.positionIndicator();
  }

  private positionIndicator() {
    const rail = this.linksRail?.nativeElement;
    if (!rail) {
      return;
    }
    const active = rail.querySelector<HTMLElement>('.nav-link.active');
    if (!active) {
      this.indicatorReady = false;
      return;
    }
    const railBox = rail.getBoundingClientRect();
    const box = active.getBoundingClientRect();
    this.indicatorLeft = box.left - railBox.left;
    this.indicatorWidth = box.width;
    this.indicatorReady = true;
  }

  logout() {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  isLoggedIn(): boolean {
    return this.authService.isLoggedIn();
  }

  isAuthPage(): boolean {
    // Pages outside the product frame (landing, auth, onboarding) get no nav
    const currentUrl = this.router.url.split('?')[0];
    return (
      currentUrl === '/' ||
      currentUrl === '/login' ||
      currentUrl === '/register' ||
      currentUrl === '/welcome'
    );
  }

  toggleMobileMenu() {
    this.mobileMenuOpen = !this.mobileMenuOpen;
  }

  closeMobileMenu() {
    this.mobileMenuOpen = false;
  }
}
