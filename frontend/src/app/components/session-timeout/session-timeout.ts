import { Component } from '@angular/core';
import { LucideLogOut, LucideTimerReset } from '@lucide/angular';
import { SessionService } from '../../services/session.service';

/**
 * Global session-timeout warning. Rendered once at the app root; shows only
 * while SessionService.warningVisible() is true, with a live countdown.
 * Styled to match the app's confirmation dialog (warm editorial ledger).
 */
@Component({
  selector: 'app-session-timeout',
  standalone: true,
  imports: [LucideTimerReset, LucideLogOut],
  templateUrl: './session-timeout.html',
  styleUrl: './session-timeout.scss'
})
export class SessionTimeoutComponent {
  constructor(public session: SessionService) {}
}
