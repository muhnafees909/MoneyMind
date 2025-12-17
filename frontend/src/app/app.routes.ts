import { Routes } from '@angular/router';
import { Login } from './components/login/login'
import { RegisterComponent } from './components/register/register.component';
import { Dashboard } from './components/dashboard/dashboard'
import { BudgetManager } from './components/budget-manager/budget-manager';
import { GoalsManagerComponent } from './components/goals-manager/goals-manager';
import { ChatComponent } from './components/chat/chat';

export const routes: Routes = [
  { path: '', redirectTo: '/login', pathMatch: 'full' },
  { path: 'login', component: Login },
  { path: 'register', component: RegisterComponent },
  { path: 'dashboard', component: Dashboard},
  { path: 'budgets', component: BudgetManager},
  { path: 'goals', component: GoalsManagerComponent },
  { path: 'chat', component: ChatComponent }

];