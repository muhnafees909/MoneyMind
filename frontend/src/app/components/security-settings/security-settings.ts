import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  LucideCheck,
  LucideKeyRound,
  LucideLock,
  LucideShieldCheck,
  LucideTriangleAlert
} from '@lucide/angular';
import { AuthService } from '../../services/auth.service';
import { ModalService } from '../../services/modal.service';

type Mode = 'idle' | 'setup' | 'backup' | 'disable';

/** Two-factor (TOTP) setup/disable card for the Profile/Settings screen. */
@Component({
  selector: 'app-security-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    LucideCheck,
    LucideKeyRound,
    LucideLock,
    LucideShieldCheck,
    LucideTriangleAlert
  ],
  templateUrl: './security-settings.html',
  styleUrl: './security-settings.scss'
})
export class SecuritySettingsComponent implements OnInit {
  loading = signal(true);
  busy = signal(false);
  mode = signal<Mode>('idle');
  error = signal('');

  mfaEnabled = signal(false);
  backupRemaining = signal(0);

  // setup state
  qrDataUri = signal('');
  secret = signal('');
  setupCode = '';

  // backup codes shown once
  backupCodes = signal<string[]>([]);
  copied = signal(false);

  // disable state
  disablePassword = '';
  disableCode = '';

  constructor(
    private auth: AuthService,
    private modal: ModalService
  ) {}

  ngOnInit() {
    this.refresh();
  }

  private refresh() {
    this.auth.mfaStatus().subscribe({
      next: (s) => {
        this.mfaEnabled.set(s.mfa_enabled);
        this.backupRemaining.set(s.backup_codes_remaining);
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }

  // ----- enable flow -----
  startSetup() {
    this.error.set('');
    this.busy.set(true);
    this.auth.mfaSetup().subscribe({
      next: (r) => {
        this.qrDataUri.set(r.qr_data_uri);
        this.secret.set(r.secret);
        this.setupCode = '';
        this.mode.set('setup');
        this.busy.set(false);
      },
      error: (e) => {
        this.busy.set(false);
        this.error.set(e.error?.message || 'Could not start setup. Try again.');
      }
    });
  }

  confirmSetup() {
    if (this.busy() || !this.setupCode.trim()) {
      return;
    }
    this.error.set('');
    this.busy.set(true);
    this.auth.mfaConfirm(this.setupCode.trim()).subscribe({
      next: (r) => {
        this.busy.set(false);
        this.backupCodes.set(r.backup_codes);
        this.mode.set('backup');
        this.mfaEnabled.set(true);
      },
      error: (e) => {
        this.busy.set(false);
        this.error.set(e.error?.message || 'That code isn’t right. Try again.');
      }
    });
  }

  copyBackup() {
    const text = this.backupCodes().join('\n');
    navigator.clipboard?.writeText(text).then(
      () => {
        this.copied.set(true);
        setTimeout(() => this.copied.set(false), 2000);
      },
      () => {}
    );
  }

  finishBackup() {
    this.mode.set('idle');
    this.backupCodes.set([]);
    this.refresh();
  }

  cancel() {
    this.mode.set('idle');
    this.error.set('');
    this.setupCode = '';
    this.disablePassword = '';
    this.disableCode = '';
  }

  // ----- disable flow -----
  startDisable() {
    this.error.set('');
    this.disablePassword = '';
    this.disableCode = '';
    this.mode.set('disable');
  }

  confirmDisable() {
    if (this.busy() || !this.disablePassword || !this.disableCode.trim()) {
      return;
    }
    this.error.set('');
    this.busy.set(true);
    this.auth.mfaDisable(this.disablePassword, this.disableCode.trim()).subscribe({
      next: () => {
        this.busy.set(false);
        this.mfaEnabled.set(false);
        this.mode.set('idle');
        this.modal.showSuccess('Two-factor authentication turned off.');
        this.refresh();
      },
      error: (e) => {
        this.busy.set(false);
        this.error.set(e.error?.message || 'Could not disable. Check your password and code.');
      }
    });
  }
}
