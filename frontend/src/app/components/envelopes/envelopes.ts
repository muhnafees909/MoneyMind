import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import {
  EnvelopeService,
  AccountReconciliation,
  EnvelopeSummary,
  IncomeEvent,
  AllocationRule
} from '../../services/envelope.service';
import { ModalService } from '../../services/modal.service';

@Component({
  selector: 'app-envelopes',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './envelopes.html',
  styleUrl: './envelopes.scss'
})
export class EnvelopesComponent implements OnInit {
  reconciliation: AccountReconciliation[] = [];
  loading = true;
  syncing = false;

  // per-goal input state for fund/withdraw
  allocationAmounts: { [goalId: number]: number | null } = {};

  // ----- paycheck prompt state -----
  incomeEvents: IncomeEvent[] = [];
  // editable split amounts per event: eventId -> goalId -> amount
  splitEdits: { [eventId: number]: { [goalId: number]: number | null } } = {};
  confirmingEvent: number | null = null;

  // ----- allocation rules state -----
  rules: AllocationRule[] = [];
  showRules = false;
  newRule: any = {
    goal_id: null,
    priority_order: 1,
    allocation_type: 'fixed_amount',
    fixed_amount: null,
    percentage: null
  };

  constructor(
    private envelopeService: EnvelopeService,
    private modalService: ModalService
  ) {}

  ngOnInit() {
    this.loadReconciliation();
    this.scanAndLoadIncomeEvents();
    this.loadRules();
  }

  loadReconciliation() {
    this.loading = true;
    this.envelopeService.getReconciliation().subscribe({
      next: (data) => {
        this.reconciliation = data;
        this.loading = false;
      },
      error: (error) => {
        console.error('Error loading reconciliation:', error);
        this.loading = false;
      }
    });
  }

  syncBalances() {
    this.syncing = true;
    this.envelopeService.syncAccounts().subscribe({
      next: () => {
        this.syncing = false;
        this.loadReconciliation();
      },
      error: (error) => {
        this.syncing = false;
        const message = error?.error?.error || 'Failed to sync balances';
        this.modalService.showError(message);
      }
    });
  }

  allocate(envelope: EnvelopeSummary, sourceType: 'manual' | 'withdrawal') {
    const amount = this.allocationAmounts[envelope.goal_id];
    if (!amount || amount <= 0) {
      this.modalService.showError('Please enter a valid amount', 'Validation Error');
      return;
    }

    this.envelopeService.createAllocation(envelope.goal_id, amount, sourceType).subscribe({
      next: () => {
        this.allocationAmounts[envelope.goal_id] = null;
        this.loadReconciliation();
      },
      error: (error) => {
        const message = error?.error?.error || 'Failed to save allocation';
        this.modalService.showError(message);
      }
    });
  }

  envelopeProgress(envelope: EnvelopeSummary): number {
    if (!envelope.target_amount) return 0;
    return Math.min((envelope.envelope_balance / envelope.target_amount) * 100, 100);
  }

  async deleteEnvelope(envelope: EnvelopeSummary) {
    const confirmed = await this.modalService.showConfirm(
      `Delete "${envelope.goal_name}"? You can restore it within 30 days.`,
      'Confirm Delete',
      'Delete',
      'Cancel'
    );
    if (!confirmed) return;

    this.envelopeService.deleteEnvelope(envelope.goal_id).subscribe({
      next: () => {
        this.modalService.showSuccess(`"${envelope.goal_name}" deleted. You can restore it from the dashboard.`, 'Envelope Deleted');
        this.loadReconciliation();
      },
      error: (error) => {
        this.modalService.showError(error?.error?.error || 'Failed to delete envelope');
      }
    });
  }

  hasAccounts(): boolean {
    return this.reconciliation.length > 0;
  }

  // ----- paycheck prompt -----

  scanAndLoadIncomeEvents() {
    this.envelopeService.scanIncomeEvents().subscribe({
      next: () => this.loadIncomeEvents(),
      error: () => this.loadIncomeEvents() // scan failing shouldn't hide existing events
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
      this.modalService.showError('Enter at least one amount to allocate', 'Validation Error');
      return;
    }
    if (this.splitRemainder(event) < 0) {
      this.modalService.showError('Split total exceeds the deposit amount', 'Validation Error');
      return;
    }

    this.confirmingEvent = event.id;
    this.envelopeService.confirmIncomeEvent(event.id, allocations).subscribe({
      next: () => {
        this.confirmingEvent = null;
        this.incomeEvents = this.incomeEvents.filter((e) => e.id !== event.id);
        this.loadReconciliation();
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

  // ----- allocation rules -----

  loadRules() {
    this.envelopeService.getRules().subscribe({
      next: (rules) => (this.rules = rules),
      error: (error) => console.error('Error loading rules:', error)
    });
  }

  linkedGoals(): EnvelopeSummary[] {
    return this.reconciliation.flatMap((entry) => entry.envelopes);
  }

  goalsWithoutRules(): EnvelopeSummary[] {
    const ruledGoalIds = new Set(this.rules.map((r) => r.goal_id));
    return this.linkedGoals().filter((g) => !ruledGoalIds.has(g.goal_id));
  }

  addRule() {
    if (!this.newRule.goal_id) {
      this.modalService.showError('Pick a goal for the rule', 'Validation Error');
      return;
    }
    this.envelopeService.createRule(this.newRule).subscribe({
      next: () => {
        this.newRule = {
          goal_id: null,
          priority_order: this.rules.length + 2,
          allocation_type: 'fixed_amount',
          fixed_amount: null,
          percentage: null
        };
        this.loadRules();
      },
      error: (error) => {
        this.modalService.showError(error?.error?.error || 'Failed to create rule');
      }
    });
  }

  toggleRule(rule: AllocationRule) {
    this.envelopeService.updateRule(rule.id, { is_active: !rule.is_active }).subscribe({
      next: () => this.loadRules(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to update rule')
    });
  }

  moveRule(rule: AllocationRule, direction: -1 | 1) {
    const sorted = [...this.rules].sort((a, b) => a.priority_order - b.priority_order);
    const index = sorted.findIndex((r) => r.id === rule.id);
    const swapWith = sorted[index + direction];
    if (!swapWith) return;

    this.envelopeService.updateRule(rule.id, { priority_order: swapWith.priority_order }).subscribe({
      next: () => {
        this.envelopeService.updateRule(swapWith.id, { priority_order: rule.priority_order }).subscribe({
          next: () => this.loadRules()
        });
      }
    });
  }

  async deleteRule(rule: AllocationRule) {
    const confirmed = await this.modalService.showConfirm(
      `Remove the rule for "${rule.goal_name}"?`, 'Confirm Delete', 'Delete', 'Cancel');
    if (!confirmed) return;
    this.envelopeService.deleteRule(rule.id).subscribe({
      next: () => this.loadRules(),
      error: (error) => this.modalService.showError(error?.error?.error || 'Failed to delete rule')
    });
  }

  ruleValueLabel(rule: AllocationRule): string {
    if (rule.allocation_type === 'fixed_amount') return `$${rule.fixed_amount}`;
    if (rule.allocation_type === 'percentage') return `${rule.percentage}%`;
    return 'Remainder';
  }
}
