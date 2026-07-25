import { Component, ElementRef, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { animate, stagger } from 'motion';
import {
  LucideCheck,
  LucideChevronDown,
  LucideChevronUp,
  LucideLandmark,
  LucideMinus,
  LucideOctagonAlert,
  LucidePencil,
  LucidePiggyBank,
  LucidePlus,
  LucideRefreshCw,
  LucideTarget,
  LucideTrash2,
  LucideTriangleAlert,
  LucideX
} from '@lucide/angular';
import {
  EnvelopeService,
  AccountReconciliation,
  EnvelopeSummary,
  IncomeEvent,
  AllocationRule,
  PlaidAccount
} from '../../services/envelope.service';
import { GoalService } from '../../services/goal.service';
import { ModalService } from '../../services/modal.service';
import { PlaidLinkService, ReauthItem } from '../../services/plaid-link.service';
import { CountUpDirective } from '../../shared/count-up.directive';

// Envelope band slots come from the shared palette (color follows the
// envelope, never its rank).
import { SLOT_COLORS } from '../../shared/category-colors';
const UNALLOCATED_COLOR = '#4a453f';

const GOAL_RING_RADIUS = 30;
const GOAL_RING_CIRCUMFERENCE = 2 * Math.PI * GOAL_RING_RADIUS;

interface BandSegment {
  key: string;
  label: string;
  value: number;
  width: number;
  color: string;
}

@Component({
  selector: 'app-envelopes',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    CountUpDirective,
    LucideCheck,
    LucideChevronDown,
    LucideChevronUp,
    LucideLandmark,
    LucideMinus,
    LucideOctagonAlert,
    LucidePencil,
    LucidePiggyBank,
    LucidePlus,
    LucideRefreshCw,
    LucideTarget,
    LucideTrash2,
    LucideTriangleAlert,
    LucideX
  ],
  templateUrl: './envelopes.html',
  styleUrl: './envelopes.scss'
})
export class EnvelopesComponent implements OnInit {
  reconciliation: AccountReconciliation[] = [];
  goals: any[] = [];
  accounts: PlaidAccount[] = [];
  rules: AllocationRule[] = [];
  incomeEvents: IncomeEvent[] = [];

  totals = { saved: 0, target: 0, envelopeCash: 0, unallocated: 0 };

  // Move-money flow (goal cards + envelope rows share it)
  moveMoneyGoalId: number | null = null;
  allocationAmounts: { [goalId: number]: number | null } = {};

  // Envelope balance correction
  editingEnvelope: number | null = null;
  editAmounts: { [goalId: number]: number | null } = {};

  // New goal panel
  showNewGoal = false;
  newGoal = {
    name: '',
    target_amount: null as number | null,
    target_date: '',
    linked_account_id: null as number | null
  };

  // Paycheck prompt
  splitEdits: { [eventId: number]: { [goalId: number]: number | null } } = {};
  confirmingEvent: number | null = null;

  // Rules
  showAddRule = false;
  newRule: any = {
    goal_id: null,
    priority_order: 1,
    allocation_type: 'fixed_amount',
    fixed_amount: null,
    percentage: null
  };

  initialLoading = true;
  revealed = false;
  preAnim = true;
  syncing = false;

  // Banks needing reconnection (from a 409, or flagged on load).
  reauthItems: ReauthItem[] = [];
  reconnectingItemId: string | null = null;

  private entranceDone = false;
  private readonly reducedMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  Math = Math;

  constructor(
    private envelopeService: EnvelopeService,
    private goalService: GoalService,
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
    this.loadAll(true);
    this.scanAndLoadIncomeEvents();
  }

  loadAll(first = false) {
    forkJoin({
      reconciliation: this.envelopeService.getReconciliation().pipe(catchError(() => of([]))),
      goals: this.goalService.getGoals().pipe(catchError(() => of([]))),
      accounts: this.envelopeService.getAccounts().pipe(catchError(() => of([]))),
      rules: this.envelopeService.getRules().pipe(catchError(() => of([])))
    }).subscribe((res) => {
      // Envelopes live only on asset accounts — liabilities are excluded here
      this.reconciliation = (res.reconciliation || []).filter((entry) =>
        this.isAssetAccount(entry.account)
      );
      this.goals = res.goals || [];
      this.accounts = res.accounts || [];
      this.rules = res.rules || [];
      // Durable reconnect prompt for any linked bank already flagged.
      this.reauthItems = this.deriveReauthFromAccounts(res.accounts || []);
      this.computeTotals();
      if (first) {
        this.initialLoading = false;
        setTimeout(() => {
          this.revealed = true;
          this.runEntrance();
        }, 40);
      }
    });
  }

  private computeTotals() {
    this.totals = {
      saved: this.goals.reduce((s, g) => s + (Number(g.current_amount) || 0), 0),
      target: this.goals.reduce((s, g) => s + (Number(g.target_amount) || 0), 0),
      envelopeCash: this.reconciliation.reduce((s, e) => s + e.allocated_total, 0),
      unallocated: this.reconciliation.reduce((s, e) => s + (e.unallocated_cash ?? 0), 0)
    };
  }

  isAssetAccount(account: PlaidAccount): boolean {
    // Single source of truth for "can back an envelope" now lives on the
    // account (backend is_envelope_eligible = depository-only)
    return account.is_envelope_eligible;
  }

  assetAccounts(): PlaidAccount[] {
    return this.accounts.filter((a) => this.isAssetAccount(a));
  }

  // ============================================
  // GOALS
  // ============================================

  isEnvelope(goal: any): boolean {
    return !!goal.linked_account_id;
  }

  goalPct(goal: any): number {
    return Math.min(Number(goal.progress_percentage) || 0, 100);
  }

  goalComplete(goal: any): boolean {
    return goal.is_completed || this.goalPct(goal) >= 100;
  }

  ringCircumference(): number {
    return GOAL_RING_CIRCUMFERENCE;
  }

  ringOffset(goal: any): number {
    return GOAL_RING_CIRCUMFERENCE * (1 - this.goalPct(goal) / 100);
  }

  toggleNewGoal() {
    this.showNewGoal = !this.showNewGoal;
    if (!this.showNewGoal) {
      this.newGoal = { name: '', target_amount: null, target_date: '', linked_account_id: null };
    }
  }

  createGoal() {
    if (!this.newGoal.name || !this.newGoal.target_amount) {
      this.modalService.showError('A goal needs a name and a target amount', 'Missing details');
      return;
    }
    const payload: any = {
      name: this.newGoal.name,
      target_amount: this.newGoal.target_amount
    };
    if (this.newGoal.target_date) {
      payload.target_date = this.newGoal.target_date;
    }
    if (this.newGoal.linked_account_id) {
      payload.linked_account_id = this.newGoal.linked_account_id;
    }
    this.goalService.createGoal(payload).subscribe({
      next: () => {
        this.toggleNewGoal();
        this.loadAll();
      },
      error: (error) => {
        this.modalService.showError(error?.error?.error || 'Failed to create goal');
      }
    });
  }

  toggleMoveMoney(goalId: number) {
    this.moveMoneyGoalId = this.moveMoneyGoalId === goalId ? null : goalId;
  }

  addMoney(goal: any) {
    const amount = this.allocationAmounts[goal.id];
    if (!amount || amount <= 0) {
      this.modalService.showError('Enter an amount above zero', 'Invalid amount');
      return;
    }
    const done = () => {
      this.allocationAmounts[goal.id] = null;
      this.moveMoneyGoalId = null;
      this.loadAll();
    };
    if (this.isEnvelope(goal)) {
      this.envelopeService.createAllocation(goal.id, amount, 'manual').subscribe({
        next: done,
        error: (error) =>
          this.modalService.showError(error?.error?.error || 'Failed to move money')
      });
    } else {
      this.goalService.addProgress(goal.id, amount).subscribe({
        next: done,
        error: (error) =>
          this.modalService.showError(error?.error?.error || 'Failed to add progress')
      });
    }
  }

  withdrawMoney(goal: any) {
    const amount = this.allocationAmounts[goal.id];
    if (!amount || amount <= 0) {
      this.modalService.showError('Enter an amount above zero', 'Invalid amount');
      return;
    }
    this.envelopeService.createAllocation(goal.id, amount, 'withdrawal').subscribe({
      next: () => {
        this.allocationAmounts[goal.id] = null;
        this.moveMoneyGoalId = null;
        this.loadAll();
      },
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to withdraw')
    });
  }

  async deleteGoal(goal: any) {
    const isEnv = this.isEnvelope(goal);
    const confirmed = await this.modalService.showConfirm(
      isEnv
        ? `Delete the "${goal.name}" envelope? Its balance returns to unallocated cash. You can restore it within 30 days.`
        : `Delete the "${goal.name}" goal? This can't be undone.`,
      'Confirm Delete',
      'Delete',
      'Cancel'
    );
    if (!confirmed) {
      return;
    }
    const request = isEnv
      ? this.envelopeService.deleteEnvelope(goal.id)
      : this.goalService.deleteGoal(goal.id);
    request.subscribe({
      next: () => this.loadAll(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to delete')
    });
  }

  accountNameFor(goal: any): string {
    return goal.linked_account_name || 'Linked account';
  }

  // ============================================
  // RECONCILIATION
  // ============================================

  syncBalances() {
    if (this.syncing) {
      return;
    }
    this.syncing = true;
    this.envelopeService.syncAccounts().subscribe({
      next: () => {
        this.syncing = false;
        this.reauthItems = [];  // everything synced cleanly
        this.loadAll();
      },
      error: (error) => {
        this.syncing = false;
        // A linked bank needs reconnection — show the calm prompt, not an error.
        if (error?.status === 409 && error.error?.error_code === 'ITEM_ACTION_REQUIRED') {
          this.reauthItems = error.error.items || [];
          this.loadAll();  // refresh balances that did come through
          return;
        }
        this.modalService.showError(error?.error?.error || 'Failed to sync balances');
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
            this.reconnectingItemId = null;
            this.syncBalances();  // retry; clears the flag on success
          },
          () => {
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

  envelopeColor(entry: AccountReconciliation, envelope: EnvelopeSummary): string {
    const index = entry.envelopes.findIndex((e) => e.goal_id === envelope.goal_id);
    return SLOT_COLORS[index % SLOT_COLORS.length];
  }

  accountBand(entry: AccountReconciliation): BandSegment[] {
    const balance = entry.actual_balance ?? entry.allocated_total;
    const base = Math.max(balance, entry.allocated_total);
    if (base <= 0) {
      return [];
    }
    const segments: BandSegment[] = entry.envelopes
      .filter((env) => env.envelope_balance > 0)
      .map((env, i) => ({
        key: `env-${env.goal_id}`,
        label: env.goal_name,
        value: env.envelope_balance,
        width: (env.envelope_balance / base) * 100,
        color: this.envelopeColor(entry, env)
      }));
    const unallocated = entry.unallocated_cash ?? 0;
    if (unallocated > 0) {
      segments.push({
        key: 'free',
        label: 'Unallocated',
        value: unallocated,
        width: (unallocated / base) * 100,
        color: UNALLOCATED_COLOR
      });
    }
    return segments;
  }

  isOverAllocated(entry: AccountReconciliation): boolean {
    return (entry.unallocated_cash ?? 0) < 0;
  }

  editEnvelope(envelope: EnvelopeSummary) {
    this.editingEnvelope = envelope.goal_id;
    this.editAmounts[envelope.goal_id] = envelope.envelope_balance;
  }

  cancelEdit() {
    this.editingEnvelope = null;
  }

  saveEnvelopeEdit(envelope: EnvelopeSummary) {
    const newAmount = this.editAmounts[envelope.goal_id];
    if (newAmount === null || newAmount === undefined || newAmount < 0) {
      this.modalService.showError('Enter a balance of zero or more', 'Invalid amount');
      return;
    }
    this.envelopeService.updateAllocation(envelope.goal_id, newAmount).subscribe({
      next: () => {
        this.editingEnvelope = null;
        this.loadAll();
      },
      error: (error) => {
        this.modalService.showError(error?.error?.error || 'Failed to update envelope');
      }
    });
  }

  goalForEnvelope(envelope: EnvelopeSummary): any {
    return this.goals.find((g) => g.id === envelope.goal_id) || { id: envelope.goal_id, linked_account_id: true, name: envelope.goal_name };
  }

  // ============================================
  // PAYCHECK PROMPT (income events)
  // ============================================

  scanAndLoadIncomeEvents() {
    this.envelopeService.scanIncomeEvents().subscribe({
      next: () => this.loadIncomeEvents(),
      error: () => this.loadIncomeEvents()
    });
  }

  loadIncomeEvents() {
    this.envelopeService.getIncomeEvents('pending').subscribe({
      next: (events) => {
        this.incomeEvents = events;
        for (const event of events) {
          this.splitEdits[event.id] = {};
          for (const row of event.suggested_split || []) {
            this.splitEdits[event.id][row.goal_id] = row.amount > 0 ? row.amount : null;
          }
        }
      },
      error: (error) => console.error('Error loading income events:', error)
    });
  }

  splitTotal(event: IncomeEvent): number {
    const edits = this.splitEdits[event.id] || {};
    return Object.values(edits).reduce((sum: number, v) => sum + (Number(v) || 0), 0);
  }

  splitRemainder(event: IncomeEvent): number {
    return Math.round((event.amount - this.splitTotal(event)) * 100) / 100;
  }

  confirmEvent(event: IncomeEvent) {
    const edits = this.splitEdits[event.id] || {};
    const allocations = Object.entries(edits)
      .map(([goalId, amount]) => ({ goal_id: +goalId, amount: Number(amount) || 0 }))
      .filter((row) => row.amount > 0);
    if (allocations.length === 0) {
      this.modalService.showError('Enter at least one amount to allocate', 'Nothing to allocate');
      return;
    }
    if (this.splitRemainder(event) < 0) {
      this.modalService.showError('Split total exceeds the deposit amount', 'Split too large');
      return;
    }
    this.confirmingEvent = event.id;
    this.envelopeService.confirmIncomeEvent(event.id, allocations).subscribe({
      next: () => {
        this.confirmingEvent = null;
        this.incomeEvents = this.incomeEvents.filter((e) => e.id !== event.id);
        this.loadAll();
      },
      error: (error) => {
        this.confirmingEvent = null;
        this.modalService.showError(error?.error?.error || 'Failed to allocate deposit');
      }
    });
  }

  dismissEvent(event: IncomeEvent) {
    this.envelopeService.dismissIncomeEvent(event.id).subscribe({
      next: () => {
        this.incomeEvents = this.incomeEvents.filter((e) => e.id !== event.id);
      },
      error: (error) => {
        this.modalService.showError(error?.error?.error || 'Failed to dismiss');
      }
    });
  }

  // ============================================
  // ALLOCATION RULES (the priority waterfall)
  // ============================================

  sortedRules(): AllocationRule[] {
    return [...this.rules].sort((a, b) => a.priority_order - b.priority_order);
  }

  linkedGoals(): EnvelopeSummary[] {
    return this.reconciliation.flatMap((entry) => entry.envelopes);
  }

  goalsWithoutRules(): EnvelopeSummary[] {
    const ruled = new Set(this.rules.map((r) => r.goal_id));
    return this.linkedGoals().filter((g) => !ruled.has(g.goal_id));
  }

  toggleAddRule() {
    this.showAddRule = !this.showAddRule;
  }

  addRule() {
    if (!this.newRule.goal_id) {
      this.modalService.showError('Pick an envelope for the rule', 'Missing envelope');
      return;
    }
    this.newRule.priority_order = this.rules.length + 1;
    this.envelopeService.createRule(this.newRule).subscribe({
      next: () => {
        this.newRule = {
          goal_id: null,
          priority_order: this.rules.length + 2,
          allocation_type: 'fixed_amount',
          fixed_amount: null,
          percentage: null
        };
        this.showAddRule = false;
        this.loadAll();
      },
      error: (error) => {
        this.modalService.showError(error?.error?.error || 'Failed to create rule');
      }
    });
  }

  toggleRule(rule: AllocationRule) {
    this.envelopeService.updateRule(rule.id, { is_active: !rule.is_active }).subscribe({
      next: () => this.loadAll(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to update rule')
    });
  }

  moveRule(rule: AllocationRule, direction: -1 | 1) {
    const sorted = this.sortedRules();
    const index = sorted.findIndex((r) => r.id === rule.id);
    const swapWith = sorted[index + direction];
    if (!swapWith) {
      return;
    }
    this.envelopeService.updateRule(rule.id, { priority_order: swapWith.priority_order }).subscribe({
      next: () => {
        this.envelopeService
          .updateRule(swapWith.id, { priority_order: rule.priority_order })
          .subscribe({ next: () => this.loadAll() });
      }
    });
  }

  async deleteRule(rule: AllocationRule) {
    const confirmed = await this.modalService.showConfirm(
      `Remove the rule for "${rule.goal_name}"? Deposits will no longer auto-fill this envelope.`,
      'Confirm Delete',
      'Delete',
      'Cancel'
    );
    if (!confirmed) {
      return;
    }
    this.envelopeService.deleteRule(rule.id).subscribe({
      next: () => this.loadAll(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to delete rule')
    });
  }

  ruleValueLabel(rule: AllocationRule): string {
    if (rule.allocation_type === 'fixed_amount') {
      return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
        rule.fixed_amount || 0
      );
    }
    if (rule.allocation_type === 'percentage') {
      return `${rule.percentage}%`;
    }
    return 'Remainder';
  }

  // ============================================
  // MOTION
  // ============================================

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
        const completed = this.host.nativeElement.querySelectorAll('.goal-card.complete .ring-svg');
        if (completed.length > 0) {
          animate(
            completed,
            { transform: ['scale(1)', 'scale(1.07)', 'scale(1)'] },
            { duration: 0.7, delay: 1, ease: 'easeInOut' }
          );
        }
      });
    });
  }
}
