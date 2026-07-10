from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from models.user import db
from models.goal import FinancialGoal
from models.envelope import EnvelopeAllocation, AllocationRule, ALLOCATION_SOURCE_TYPES, ALLOCATION_RULE_TYPES
from models.plaid_account import PlaidAccount
from models.transaction import Transaction
from models.income_event import IncomeEvent
from utils.income import record_income_event, compute_suggested_split

envelopes_bp = Blueprint('envelopes', __name__)


def envelope_balance(goal_id):
    """Sum of the allocation ledger for one goal."""
    total = db.session.query(func.coalesce(func.sum(EnvelopeAllocation.amount), 0)) \
        .filter(EnvelopeAllocation.goal_id == goal_id).scalar()
    return Decimal(total)


def apply_allocation(goal, amount, source_type, note=None, source_transaction_id=None):
    """Write one ledger row and keep goal.current_amount in sync (same DB transaction).
    Caller is responsible for db.session.commit()."""
    allocation = EnvelopeAllocation(
        goal_id=goal.id,
        amount=amount,
        source_type=source_type,
        note=note,
        source_transaction_id=source_transaction_id
    )
    db.session.add(allocation)

    goal.current_amount = Decimal(goal.current_amount) + amount
    if goal.current_amount >= goal.target_amount and not goal.is_completed:
        goal.is_completed = True
        goal.completed_at = datetime.combine(date.today(), datetime.min.time())
    elif goal.current_amount < goal.target_amount and goal.is_completed:
        goal.is_completed = False
        goal.completed_at = None
    return allocation


def parse_amount(raw):
    """Parse a positive money amount; returns Decimal or None if invalid."""
    try:
        amount = Decimal(str(raw)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return amount


@envelopes_bp.route('/accounts', methods=['GET'])
@jwt_required()
def get_accounts():
    """List the user's synced Plaid accounts (for linking goals + reconciliation)"""
    user_id = get_jwt_identity()
    accounts = PlaidAccount.query.filter_by(user_id=int(user_id)).order_by(PlaidAccount.name).all()
    return jsonify([a.to_dict() for a in accounts]), 200


@envelopes_bp.route('/allocations', methods=['POST'])
@jwt_required()
def create_allocation():
    """Manually move money into (or out of) a goal's envelope.
    Body: {goal_id, amount > 0, source_type: 'manual'|'withdrawal'|'correction', note?}"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    goal = FinancialGoal.query.filter_by(id=data.get('goal_id'), user_id=int(user_id)).first()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    if not goal.linked_account_id:
        return jsonify({'error': 'Goal is not linked to an account. Link it to an account to use envelopes.'}), 400

    source_type = data.get('source_type', 'manual')
    if source_type not in ('manual', 'withdrawal', 'correction'):
        return jsonify({'error': f'source_type must be one of manual, withdrawal, correction'}), 400

    amount = parse_amount(data.get('amount'))
    if amount is None:
        return jsonify({'error': 'Valid positive amount required'}), 400

    # Withdrawals are stored as negative ledger rows
    if source_type == 'withdrawal':
        current = envelope_balance(goal.id)
        if amount > current:
            return jsonify({'error': f'Cannot withdraw ${amount} — envelope only holds ${current}'}), 400
        amount = -amount

    allocation = apply_allocation(goal, amount, source_type, note=data.get('note'))
    db.session.commit()

    return jsonify({
        'allocation': allocation.to_dict(),
        'goal': goal.to_dict(),
        'envelope_balance': float(envelope_balance(goal.id))
    }), 201


@envelopes_bp.route('/allocations', methods=['GET'])
@jwt_required()
def list_allocations():
    """Allocation history, optionally filtered by goal_id"""
    user_id = get_jwt_identity()
    query = EnvelopeAllocation.query.join(FinancialGoal) \
        .filter(FinancialGoal.user_id == int(user_id))

    goal_id = request.args.get('goal_id', type=int)
    if goal_id:
        query = query.filter(EnvelopeAllocation.goal_id == goal_id)

    limit = min(request.args.get('limit', default=50, type=int), 200)
    allocations = query.order_by(EnvelopeAllocation.created_at.desc()).limit(limit).all()
    return jsonify([a.to_dict() for a in allocations]), 200


@envelopes_bp.route('/reconciliation', methods=['GET'])
@jwt_required()
def reconciliation():
    """Per linked account: actual bank balance vs sum of envelope balances vs unallocated cash"""
    user_id = get_jwt_identity()
    accounts = PlaidAccount.query.filter_by(user_id=int(user_id)).all()

    result = []
    for account in accounts:
        envelopes = []
        allocated_total = Decimal('0')
        goals = FinancialGoal.query.filter_by(
            user_id=int(user_id), linked_account_id=account.id
        ).order_by(FinancialGoal.priority_order.asc().nullslast(), FinancialGoal.created_at.asc()).all()

        for goal in goals:
            balance = envelope_balance(goal.id)
            allocated_total += balance
            envelopes.append({
                'goal_id': goal.id,
                'goal_name': goal.name,
                'target_amount': float(goal.target_amount),
                'priority_order': goal.priority_order,
                'envelope_balance': float(balance),
                # drift between ledger and the cached counter — should stay 0
                'counter_drift': float(Decimal(goal.current_amount) - balance)
            })

        actual = Decimal(account.current_balance) if account.current_balance is not None else None
        result.append({
            'account': account.to_dict(),
            'envelopes': envelopes,
            'allocated_total': float(allocated_total),
            'actual_balance': float(actual) if actual is not None else None,
            'unallocated_cash': float(actual - allocated_total) if actual is not None else None
        })

    return jsonify(result), 200


# ---------- Income events (paycheck detection + allocation prompt) ----------

@envelopes_bp.route('/income-events', methods=['GET'])
@jwt_required()
def get_income_events():
    """Pending (default) or all income events, each with a suggested split
    pre-filled from the user's allocation rules."""
    user_id = get_jwt_identity()
    status = request.args.get('status', 'pending')

    query = IncomeEvent.query.filter_by(user_id=int(user_id))
    if status != 'all':
        query = query.filter_by(status=status)
    events = query.order_by(IncomeEvent.detected_at.desc()).limit(20).all()

    result = []
    for event in events:
        payload = event.to_dict()
        if event.status == 'pending':
            split, remainder = compute_suggested_split(int(user_id), Decimal(event.amount))
            payload['suggested_split'] = split
            payload['unallocated_remainder'] = float(remainder)
        result.append(payload)
    return jsonify(result), 200


@envelopes_bp.route('/income-events/scan', methods=['POST'])
@jwt_required()
def scan_income_events():
    """Re-scan recent Plaid transactions for likely income deposits that don't
    have an income event yet. Idempotent — safe to call on page load."""
    user_id = get_jwt_identity()
    recent = Transaction.query.filter_by(
        user_id=int(user_id), transaction_type='income', source='plaid'
    ).order_by(Transaction.transaction_date.desc()).limit(100).all()

    created = 0
    for transaction in recent:
        if record_income_event(transaction):
            created += 1
    db.session.commit()

    return jsonify({'created': created}), 200


@envelopes_bp.route('/income-events/<int:event_id>/confirm', methods=['POST'])
@jwt_required()
def confirm_income_event(event_id):
    """Apply the user's (possibly edited) split: one paycheck_split allocation
    per goal, all tied back to the source deposit transaction."""
    user_id = get_jwt_identity()
    event = IncomeEvent.query.filter_by(id=event_id, user_id=int(user_id)).first()
    if not event:
        return jsonify({'error': 'Income event not found'}), 404
    if event.status != 'pending':
        return jsonify({'error': f'Income event already {event.status}'}), 400

    data = request.get_json() or {}
    rows = data.get('allocations') or []
    if not rows:
        return jsonify({'error': 'allocations list required'}), 400

    parsed = []
    total = Decimal('0')
    for row in rows:
        amount = parse_amount(row.get('amount'))
        if amount is None:
            continue  # zero/blank rows are simply skipped
        goal = FinancialGoal.query.filter_by(id=row.get('goal_id'), user_id=int(user_id)).first()
        if not goal:
            return jsonify({'error': f"Goal {row.get('goal_id')} not found"}), 404
        if not goal.linked_account_id:
            return jsonify({'error': f'Goal "{goal.name}" is not linked to an account'}), 400
        parsed.append((goal, amount))
        total += amount

    if not parsed:
        return jsonify({'error': 'No positive allocation amounts provided'}), 400
    if total > Decimal(event.amount):
        return jsonify({'error': f'Split total ${total} exceeds the deposit amount ${event.amount}'}), 400

    for goal, amount in parsed:
        apply_allocation(goal, amount, 'paycheck_split',
                         note='Paycheck split',
                         source_transaction_id=event.transaction_id)

    event.status = 'confirmed'
    event.resolved_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'event': event.to_dict(),
        'allocated_total': float(total),
        'goals': [goal.to_dict() for goal, _ in parsed]
    }), 200


@envelopes_bp.route('/income-events/<int:event_id>/dismiss', methods=['POST'])
@jwt_required()
def dismiss_income_event(event_id):
    """Not a paycheck (or user doesn't want to allocate it) — hide the prompt."""
    user_id = get_jwt_identity()
    event = IncomeEvent.query.filter_by(id=event_id, user_id=int(user_id)).first()
    if not event:
        return jsonify({'error': 'Income event not found'}), 404
    if event.status != 'pending':
        return jsonify({'error': f'Income event already {event.status}'}), 400

    event.status = 'dismissed'
    event.resolved_at = datetime.utcnow()
    db.session.commit()
    return jsonify(event.to_dict()), 200


# ---------- Allocation rules (waterfall used by Phase 2 paycheck prompt) ----------

@envelopes_bp.route('/rules', methods=['GET'])
@jwt_required()
def get_rules():
    user_id = get_jwt_identity()
    rules = AllocationRule.query.filter_by(user_id=int(user_id)) \
        .order_by(AllocationRule.priority_order.asc()).all()
    return jsonify([r.to_dict() for r in rules]), 200


@envelopes_bp.route('/rules', methods=['POST'])
@jwt_required()
def create_rule():
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    goal = FinancialGoal.query.filter_by(id=data.get('goal_id'), user_id=int(user_id)).first()
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404

    allocation_type = data.get('allocation_type')
    if allocation_type not in ALLOCATION_RULE_TYPES:
        return jsonify({'error': f'allocation_type must be one of {", ".join(ALLOCATION_RULE_TYPES)}'}), 400

    error = _validate_rule_amounts(allocation_type, data)
    if error:
        return jsonify({'error': error}), 400

    if AllocationRule.query.filter_by(user_id=int(user_id), goal_id=goal.id).first():
        return jsonify({'error': 'A rule already exists for this goal. Update it instead.'}), 400

    rule = AllocationRule(
        user_id=int(user_id),
        goal_id=goal.id,
        priority_order=data.get('priority_order', 1),
        allocation_type=allocation_type,
        fixed_amount=data.get('fixed_amount'),
        percentage=data.get('percentage'),
        is_active=data.get('is_active', True)
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify(rule.to_dict()), 201


@envelopes_bp.route('/rules/<int:rule_id>', methods=['PUT'])
@jwt_required()
def update_rule(rule_id):
    user_id = get_jwt_identity()
    rule = AllocationRule.query.filter_by(id=rule_id, user_id=int(user_id)).first()
    if not rule:
        return jsonify({'error': 'Rule not found'}), 404

    data = request.get_json() or {}
    if 'allocation_type' in data:
        if data['allocation_type'] not in ALLOCATION_RULE_TYPES:
            return jsonify({'error': f'allocation_type must be one of {", ".join(ALLOCATION_RULE_TYPES)}'}), 400
        rule.allocation_type = data['allocation_type']

    error = _validate_rule_amounts(rule.allocation_type, data, existing=rule)
    if error:
        return jsonify({'error': error}), 400

    for field in ('priority_order', 'fixed_amount', 'percentage', 'is_active'):
        if field in data:
            setattr(rule, field, data[field])

    db.session.commit()
    return jsonify(rule.to_dict()), 200


@envelopes_bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@jwt_required()
def delete_rule(rule_id):
    user_id = get_jwt_identity()
    rule = AllocationRule.query.filter_by(id=rule_id, user_id=int(user_id)).first()
    if not rule:
        return jsonify({'error': 'Rule not found'}), 404
    db.session.delete(rule)
    db.session.commit()
    return jsonify({'message': 'Rule deleted'}), 200


def _validate_rule_amounts(allocation_type, data, existing=None):
    """fixed_amount rules need a positive fixed_amount; percentage rules need 0 < pct <= 100."""
    if allocation_type == 'fixed_amount':
        value = data.get('fixed_amount', existing.fixed_amount if existing else None)
        if value is None or parse_amount(value) is None:
            return 'fixed_amount rules require a positive fixed_amount'
    if allocation_type == 'percentage':
        value = data.get('percentage', existing.percentage if existing else None)
        try:
            pct = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return 'percentage rules require a percentage between 0 and 100'
        if pct <= 0 or pct > 100:
            return 'percentage rules require a percentage between 0 and 100'
    return None
