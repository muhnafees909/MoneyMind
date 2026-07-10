# MoneyMind: Envelope Allocation + Recurring Expenses — Data Model

## Design summary

Two new feature areas that share infrastructure:

1. **Envelopes** — virtual sub-allocations within a real (Plaid-linked) account, so "$8,400 in HYSA" becomes "Hajj $2,000 / Marriage $3,500 / Emergency $2,400 / $500 unallocated."
2. **Recurring Expenses** — pattern-detected recurring charges, linked to Budget categories but tracked on their own timeline.

Both rely on the same underlying pattern: **watch the Plaid transaction stream → detect a candidate event → prompt the user to confirm/allocate → persist a structured record.**

---

## 1. Envelope Allocation

### Entities

```sql
-- Extends the existing "goals" concept. If your current Goal table
-- already has (id, user_id, name, target_amount, target_date, status),
-- add these columns rather than creating a new table:

ALTER TABLE goals
  ADD COLUMN linked_account_id UUID REFERENCES accounts(id), -- nullable; envelope mode on if set
  ADD COLUMN priority_order INT DEFAULT NULL; -- rank in the allocation waterfall (1 = first funded)

-- New: every dollar that moves into/out of an envelope is a discrete record,
-- not just a running counter. This gives you an audit trail and lets the
-- reconciliation view work.
CREATE TABLE envelope_allocations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  amount NUMERIC(12,2) NOT NULL,          -- positive = funded, negative = withdrawn/spent
  source_transaction_id UUID REFERENCES transactions(id), -- nullable; set if triggered by a Plaid deposit
  source_type VARCHAR(20) NOT NULL,        -- 'paycheck_split' | 'manual' | 'withdrawal' | 'correction'
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_envelope_allocations_goal ON envelope_allocations(goal_id);

-- New: captures the priority-ordered waterfall itself, so it's editable
-- without redeploying code (mirrors your own emergency fund -> Roth IRA ->
-- marriage HYSA -> Hajj -> house -> halal brokerage system)
CREATE TABLE allocation_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  goal_id UUID NOT NULL REFERENCES goals(id),
  priority_order INT NOT NULL,
  allocation_type VARCHAR(10) NOT NULL,   -- 'fixed_amount' | 'percentage' | 'remainder'
  fixed_amount NUMERIC(12,2),             -- used if allocation_type = fixed_amount
  percentage NUMERIC(5,2),                -- used if allocation_type = percentage
  is_active BOOLEAN DEFAULT true
);
```

### Derived fields (computed, not stored)

- `envelope_balance(goal_id)` = `SUM(envelope_allocations.amount) WHERE goal_id = ?`
- `account_actual_balance(account_id)` = latest Plaid balance for the account
- `unallocated_cash(account_id)` = `account_actual_balance - SUM(envelope_balance for all goals linked to that account)`

This last one is your **reconciliation view** — the number that tells you if something's off (spent from the account outside the app, interest accrued, etc).

### Flow: paycheck deposit → allocation prompt

1. Plaid webhook lands a new transaction on the linked account, `amount > 0`, matching a "likely income" heuristic (recurring payer, positive amount, round-ish timing).
2. App checks `allocation_rules` for that account's goals, ordered by `priority_order`.
3. Surface a confirmation UI pre-filled with the suggested split (fixed amounts first, then percentages, remainder last).
4. On confirm, write one `envelope_allocations` row per goal, each with `source_transaction_id` set to the deposit.

---

## 2. Recurring Expenses

### Entities

```sql
CREATE TABLE recurring_expenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  merchant_name VARCHAR(255) NOT NULL,
  budget_category_id UUID REFERENCES budget_categories(id), -- links back to existing Budget tab
  expected_amount NUMERIC(12,2) NOT NULL,
  cadence VARCHAR(20) NOT NULL,            -- 'weekly' | 'monthly' | 'annual' | 'irregular'
  next_expected_date DATE,
  status VARCHAR(20) DEFAULT 'active',     -- 'active' | 'dismissed' | 'cancelled_by_user'
  detected_at TIMESTAMPTZ DEFAULT now(),
  confirmed_by_user BOOLEAN DEFAULT false
);

-- Links each actual transaction to the recurring series it belongs to,
-- so you can compute drift (price creep) and confidence over time
CREATE TABLE recurring_expense_occurrences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recurring_expense_id UUID NOT NULL REFERENCES recurring_expenses(id) ON DELETE CASCADE,
  transaction_id UUID NOT NULL REFERENCES transactions(id),
  amount NUMERIC(12,2) NOT NULL,
  occurred_at DATE NOT NULL
);
```

### Detection logic (batch job or on new-transaction trigger)

Group historical transactions by `(merchant_name, rounded_amount)`, then flag as a recurring **candidate** if:
- ≥ 3 occurrences exist, AND
- intervals between occurrences are consistent (± a few days) for weekly/monthly, or ~365 days for annual, AND
- amount varies by less than ~15% across occurrences (catches subscriptions with tax/fee drift, still excludes one-off similar charges).

Candidates get inserted as `recurring_expenses` with `confirmed_by_user = false`; surface them in a "review" queue rather than auto-activating, so you're not falsely flagging things like biweekly grocery runs.

### Price creep flag

On each new `recurring_expense_occurrences` insert, compare `amount` to the average of the last 3 occurrences for that series. If it jumps > ~10%, surface a "this recurring charge went up" notice.

### UI relationship to Budget tab

- **Recurring screen**: standalone list — merchant, cadence, next expected date, amount, linked category, running total.
- **Budget tab**: each category shows a small subtotal like "Recurring: $86 of $400 budgeted" so recurring commitments are visible in context without duplicating the full recurring UI there.

---

## Suggested build order

1. `envelope_allocations` + `allocation_rules` tables, reconciliation view, manual allocation only (no auto-detection yet) — gets you the "how much do I actually have for Hajj" answer immediately.
2. Paycheck-detection trigger + allocation prompt — automates step 1.
3. `recurring_expenses` detection job + review queue UI.
4. Budget tab integration (recurring subtotal badge).

Steps 1–2 and 3 can be built in parallel if you want to split work across two Claude Code sessions.