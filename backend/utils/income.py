"""Income-deposit detection and the allocation waterfall used to pre-fill
the paycheck split prompt."""
from decimal import Decimal, ROUND_DOWN
from models.user import db
from models.transaction import Transaction
from models.goal import FinancialGoal
from models.envelope import AllocationRule
from models.income_event import IncomeEvent

# Deposits below this are ignored (interest, tiny refunds)
MIN_INCOME_AMOUNT = Decimal('100')

# Substrings that strongly suggest a payroll/income deposit
INCOME_KEYWORDS = ('payroll', 'direct dep', 'dir dep', 'deposit from employer',
                   'salary', 'paycheck', 'wages', 'gusto', 'adp')

# How many prior deposits from the same payer make it "recurring"
RECURRING_PAYER_MIN_PRIORS = 2


def is_likely_income(transaction: Transaction) -> bool:
    """Heuristic: is this transaction probably a paycheck-style deposit?

    Gates: must be an income-type, Plaid-synced transaction of at least
    MIN_INCOME_AMOUNT. Then any one strong signal qualifies it:
    - Plaid categorized it as INCOME
    - the description contains a payroll keyword
    - the same payer has deposited money repeatedly before
    """
    if transaction.transaction_type != 'income':
        return False
    if transaction.source != 'plaid':
        return False
    if Decimal(transaction.amount) < MIN_INCOME_AMOUNT:
        return False

    if (transaction.category or '').upper().startswith('INCOME'):
        return True

    description = (transaction.description or '').lower()
    if any(keyword in description for keyword in INCOME_KEYWORDS):
        return True

    prior_deposits = Transaction.query.filter(
        Transaction.user_id == transaction.user_id,
        Transaction.description == transaction.description,
        Transaction.transaction_type == 'income',
        Transaction.id != transaction.id
    ).count()
    return prior_deposits >= RECURRING_PAYER_MIN_PRIORS


def record_income_event(transaction: Transaction):
    """Create a pending IncomeEvent for a transaction if it looks like income
    and hasn't been recorded yet. Does not commit. Returns the event or None."""
    if not is_likely_income(transaction):
        return None
    if IncomeEvent.query.filter_by(transaction_id=transaction.id).first():
        return None

    event = IncomeEvent(
        user_id=transaction.user_id,
        transaction_id=transaction.id,
        plaid_account_id=transaction.plaid_account_id,
        amount=Decimal(transaction.amount)
    )
    db.session.add(event)
    return event


def compute_suggested_split(user_id: int, amount: Decimal):
    """Pre-fill a deposit split from the user's allocation rules.

    Waterfall order (matching the design doc): fixed amounts by priority,
    then percentages of the gross deposit by priority, then remainder rules
    share whatever is left. Each envelope is also capped at what its goal
    still needs. Linked goals without a rule are included at $0 so the user
    can adjust manually.

    Returns (split_rows, unallocated_remainder).
    """
    amount = Decimal(amount)
    goals = FinancialGoal.query.filter(
        FinancialGoal.user_id == user_id,
        FinancialGoal.linked_account_id.isnot(None),
        FinancialGoal.is_completed.is_(False)
    ).all()
    goals_by_id = {g.id: g for g in goals}
    if not goals_by_id:
        return [], amount

    rules = AllocationRule.query.filter(
        AllocationRule.user_id == user_id,
        AllocationRule.is_active.is_(True),
        AllocationRule.goal_id.in_(goals_by_id.keys())
    ).order_by(AllocationRule.priority_order.asc()).all()

    remaining = amount
    split = []
    seen_goal_ids = set()

    def goal_headroom(goal):
        return max(Decimal(goal.target_amount) - Decimal(goal.current_amount), Decimal('0'))

    def add_row(goal, allocated, rule_type):
        nonlocal remaining
        remaining -= allocated
        seen_goal_ids.add(goal.id)
        split.append({
            'goal_id': goal.id,
            'goal_name': goal.name,
            'amount': float(allocated),
            'rule_type': rule_type
        })

    fixed_rules = [r for r in rules if r.allocation_type == 'fixed_amount']
    percentage_rules = [r for r in rules if r.allocation_type == 'percentage']
    remainder_rules = [r for r in rules if r.allocation_type == 'remainder']

    for rule in fixed_rules:
        goal = goals_by_id[rule.goal_id]
        allocated = min(Decimal(rule.fixed_amount), goal_headroom(goal), remaining)
        add_row(goal, max(allocated, Decimal('0')), 'fixed_amount')

    for rule in percentage_rules:
        goal = goals_by_id[rule.goal_id]
        share = (Decimal(rule.percentage) / 100 * amount).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        allocated = min(share, goal_headroom(goal), remaining)
        add_row(goal, max(allocated, Decimal('0')), 'percentage')

    if remainder_rules and remaining > 0:
        per_rule = (remaining / len(remainder_rules)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        for rule in remainder_rules:
            goal = goals_by_id[rule.goal_id]
            allocated = min(per_rule, goal_headroom(goal), remaining)
            add_row(goal, max(allocated, Decimal('0')), 'remainder')
    else:
        for rule in remainder_rules:
            add_row(goals_by_id[rule.goal_id], Decimal('0'), 'remainder')

    # Linked goals with no rule: include at $0 for manual adjustment
    for goal in goals:
        if goal.id not in seen_goal_ids:
            split.append({
                'goal_id': goal.id,
                'goal_name': goal.name,
                'amount': 0.0,
                'rule_type': None
            })

    return split, remaining
