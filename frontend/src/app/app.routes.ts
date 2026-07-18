import { Routes } from '@angular/router';
import { LandingComponent } from './components/landing/landing';
import { Login } from './components/login/login'
import { RegisterComponent } from './components/register/register.component';
import { Dashboard } from './components/dashboard/dashboard'
import { TransactionsComponent } from './components/transactions/transactions';
import { BudgetManager } from './components/budget-manager/budget-manager';
import { EnvelopesComponent } from './components/envelopes/envelopes';
import { RecurringComponent } from './components/recurring/recurring';
import { ChatComponent } from './components/chat/chat';
import { ProfileComponent } from './components/profile/profile';
import { LegalComponent } from './components/legal/legal';
import { OnboardingComponent } from './components/onboarding/onboarding';
import { authGuard } from './guards/auth.guard';
import { guestGuard } from './guards/guest.guard';

export const routes: Routes = [
  { path: '', component: LandingComponent, pathMatch: 'full' },
  // Auth pages: public, but signed-in users get bounced to the dashboard
  { path: 'login', component: Login, canActivate: [guestGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [guestGuard] },
  // Terms of Service & Privacy Policy — public, no guard
  { path: 'legal', component: LegalComponent },
  // One-time optional setup after account creation; skippable, revisitable
  { path: 'welcome', component: OnboardingComponent, canActivate: [authGuard] },
  { path: 'dashboard', component: Dashboard, canActivate: [authGuard] },
  { path: 'transactions', component: TransactionsComponent, canActivate: [authGuard] },
  { path: 'budgets', component: BudgetManager, canActivate: [authGuard] },
  // Goals and Envelopes are one screen now; keep the old path working
  { path: 'goals', redirectTo: '/envelopes', pathMatch: 'full' },
  { path: 'envelopes', component: EnvelopesComponent, canActivate: [authGuard] },
  { path: 'recurring', component: RecurringComponent, canActivate: [authGuard] },
  { path: 'chat', component: ChatComponent, canActivate: [authGuard] },
  { path: 'profile', component: ProfileComponent, canActivate: [authGuard] }

];