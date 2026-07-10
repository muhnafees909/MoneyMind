import { Routes } from '@angular/router';
import { Login } from './components/login/login'
import { RegisterComponent } from './components/register/register.component';
import { Dashboard } from './components/dashboard/dashboard'
import { BudgetManager } from './components/budget-manager/budget-manager';
import { GoalsManagerComponent } from './components/goals-manager/goals-manager';
import { EnvelopesComponent } from './components/envelopes/envelopes';
import { RecurringComponent } from './components/recurring/recurring';
import { ChatComponent } from './components/chat/chat';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: '/login', pathMatch: 'full' },
  { path: 'login', component: Login },
  { path: 'register', component: RegisterComponent },
  { path: 'dashboard', component: Dashboard, canActivate: [authGuard] },
  { path: 'budgets', component: BudgetManager, canActivate: [authGuard] },
  { path: 'goals', component: GoalsManagerComponent, canActivate: [authGuard] },
  { path: 'envelopes', component: EnvelopesComponent, canActivate: [authGuard] },
  { path: 'recurring', component: RecurringComponent, canActivate: [authGuard] },
  { path: 'chat', component: ChatComponent, canActivate: [authGuard] }

];