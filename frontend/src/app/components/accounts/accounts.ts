import { Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { animate, stagger } from 'motion';
import {
  LucideBan,
  LucideCheck,
  LucideCreditCard,
  LucideInbox,
  LucideLandmark,
  LucidePencil,
  LucideRefreshCw,
  LucideTriangleAlert,
  LucideWallet,
  LucideX
} from '@lucide/angular';
import { AccountService } from '../../services/account.service';
import { PlaidAccount } from '../../services/envelope.service';
import { ModalService } from '../../services/modal.service';
import { PlaidLinkService, ReauthItem } from '../../services/plaid-link.service';
import { CountUpDirective } from '../../shared/count-up.directive';

@Component({
  selector: 'app-accounts',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    CountUpDirective,
    LucideBan,
    LucideCheck,
    LucideCreditCard,
    LucideInbox,
    LucideLandmark,
    LucidePencil,
    LucideRefreshCw,
    LucideTriangleAlert,
    LucideWallet,
    LucideX
  ],
  templateUrl: './accounts.html',
  styleUrl: './accounts.scss'
})
export class AccountsComponent implements OnInit {
  accounts: PlaidAccount[] = [];
  initialLoading = true;
  syncing = false;

  // Banks that need the user to reconnect (from a 409, or flagged on load).
  reauthItems: ReauthItem[] = [];
  reconnectingItemId: string | null = null;

  // Inline rename state
  editingId: number | null = null;
  editValue = '';
  savingId: number | null = null;

  preAnim = true;
  private entranceDone = false;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor(
    private accountService: AccountService,
    private modalService: ModalService,
    private plaidLink: PlaidLinkService,
    private zone: NgZone,
    private host: ElementRef<HTMLElement>
  ) {
    if (this.reducedMotion) {
      this.preAnim = false;
    }
  }

  ngOnInit() {
    this.load();
  }

  private load() {
    this.accountService.getAccounts().subscribe({
      next: (accounts) => {
        this.accounts = accounts;
        // Surface a durable reconnect prompt for any bank already flagged,
        // without waiting for the user to hit Refresh.
        this.reauthItems = this.deriveReauthFromAccounts(accounts);
        this.finishLoad();
      },
      error: () => {
        this.modalService.showError('Could not load your accounts. Try again shortly.');
        this.finishLoad();
      }
    });
  }

  /** Build one reconnect prompt per flagged item from the accounts list. */
  private deriveReauthFromAccounts(accounts: PlaidAccount[]): ReauthItem[] {
    const byItem = new Map<string, ReauthItem>();
    for (const a of accounts) {
      if (a.needs_reauth && a.item_id && !byItem.has(a.item_id)) {
        const bank = a.institution_name || 'your bank';
        byItem.set(a.item_id, {
          item_id: a.item_id,
          institution_name: a.institution_name,
          error_code: 'ITEM_LOGIN_REQUIRED',
          message: `Your connection to ${bank} needs to be reconnected.`,
          reconnect: true
        });
      }
    }
    return [...byItem.values()];
  }

  private finishLoad() {
    this.initialLoading = false;
    setTimeout(() => this.runEntrance(), 40);
  }

  syncAccounts() {
    if (this.syncing) {
      return;
    }
    this.syncing = true;
    this.accountService.syncAccounts().subscribe({
      next: (res) => {
        this.syncing = false;
        this.accounts = res.accounts;
        this.reauthItems = [];  // everything synced cleanly
        this.modalService.showSuccess(res.message || 'Accounts refreshed');
      },
      error: (error) => {
        this.syncing = false;
        // A bank (or several) needs the user to reconnect — show the calm
        // prompt instead of a raw error, and keep any balances that did sync.
        if (error?.status === 409 && error.error?.error_code === 'ITEM_ACTION_REQUIRED') {
          this.reauthItems = error.error.items || [];
          if (error.error.accounts) {
            this.accounts = error.error.accounts;
          }
          return;
        }
        this.modalService.showError(
          error?.error?.error || 'Could not refresh — connect a bank from the dashboard first.'
        );
      }
    });
  }

  /** Relaunch Plaid Link in update mode for a flagged item, then retry sync. */
  reconnect(item: ReauthItem) {
    if (this.reconnectingItemId) {
      return;
    }
    this.reconnectingItemId = item.item_id;
    this.plaidLink.createUpdateLinkToken(item.item_id).subscribe({
      next: (res) => {
        this.plaidLink.open(
          res.link_token,
          () => {
            // Re-auth completed — retry the sync, which clears the flag on success.
            this.reconnectingItemId = null;
            this.syncAccounts();
          },
          () => {
            // User dismissed Link without finishing — leave the prompt in place.
            this.reconnectingItemId = null;
          }
        );
      },
      error: (error) => {
        this.reconnectingItemId = null;
        this.modalService.showError(
          error?.error?.error || 'Could not start reconnecting. Please try again.'
        );
      }
    });
  }

  // ============================================
  // INLINE RENAME
  // ============================================

  startEdit(account: PlaidAccount) {
    if (this.savingId !== null) {
      return;
    }
    this.editingId = account.id;
    this.editValue = account.nickname || '';
    setTimeout(() => {
      this.host.nativeElement.querySelector<HTMLInputElement>('.rename-input')?.focus();
    });
  }

  cancelEdit() {
    this.editingId = null;
    this.editValue = '';
  }

  saveEdit(account: PlaidAccount) {
    const trimmed = this.editValue.trim();
    // No-op if unchanged (both empty, or same as current nickname)
    if (trimmed === (account.nickname || '')) {
      this.cancelEdit();
      return;
    }

    this.savingId = account.id;
    this.accountService.rename(account.id, trimmed).subscribe({
      next: (updated) => {
        Object.assign(account, updated);
        this.savingId = null;
        this.editingId = null;
        this.editValue = '';
      },
      error: (error) => {
        this.savingId = null;
        this.modalService.showError(error?.error?.error || 'Could not rename — try again.');
      }
    });
  }

  clearNickname(account: PlaidAccount) {
    this.savingId = account.id;
    this.accountService.rename(account.id, null).subscribe({
      next: (updated) => {
        Object.assign(account, updated);
        this.savingId = null;
        this.editingId = null;
      },
      error: (error) => {
        this.savingId = null;
        this.modalService.showError(error?.error?.error || 'Could not reset the name — try again.');
      }
    });
  }

  onRenameKeydown(event: KeyboardEvent, account: PlaidAccount) {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.saveEdit(account);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.cancelEdit();
    }
  }

  // ============================================
  // DISPLAY HELPERS
  // ============================================

  accountKind(account: PlaidAccount): string {
    const type = (account.account_type || '').toLowerCase();
    const subtype = account.account_subtype;
    if (subtype) {
      // "checking" → "Checking", "credit card" → "Credit card"
      return subtype.charAt(0).toUpperCase() + subtype.slice(1);
    }
    if (type === 'depository') return 'Bank account';
    if (type === 'credit') return 'Credit card';
    if (type === 'loan') return 'Loan';
    return 'Account';
  }

  balanceLabel(account: PlaidAccount): string {
    return account.is_liability ? 'Balance owed' : 'Current balance';
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
