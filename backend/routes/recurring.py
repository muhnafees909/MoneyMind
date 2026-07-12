from collections import Counter
from decimal import Decimal
from datetime import timedelta, date
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.transaction import Transaction
from models.recurring import RecurringExpense, RecurringExpenseOccurrence, RECURRING_CADENCES
from utils.recurring import (
    detect_recurring, cadence_nominal_days, normalize_merchant, infer_cadence,
    _attach_occurrences,
)

recurring_bp = Blueprint('recurring', __name__)


@recurring_bp.route('/manual', methods=['POST'])
@jwt_required()
def create_manual_recurring():
    """Create a manual recurring expense entry for tracking (e.g. rent if only 1-2 historical transactions).
    Body: {category, expected_amount, cadence, description?}"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    # Validate required fields
    if not data.get('category'):
        return jsonify({'error': 'category required'}), 400
    if 'expected_amount' not in data:
        return jsonify({'error': 'expected_amount required'}), 400
    if not data.get('cadence'):
        return jsonify({'error': 'cadence required'}), 400
    if data['cadence'] not in RECURRING_CADENCES:
        return jsonify({'error': f'cadence must be one of {", ".join(RECURRING_CADENCES)}'}), 400

    try:
        amount = Decimal(str(data['expected_amount']))
    except Exception:
        return jsonify({'error': 'Invalid expected_amount'}), 400
    if amount <= 0:
        return jsonify({'error': 'expected_amount must be positive'}), 400

    merchant_name = data.get('description', 'Manual Entry')

    # Anchor a schedule so amount+date-window matching can catch future charges,
    # even without a historical transaction to seed from.
    anchor = data.get('next_expected_date')
    if anchor:
        try:
            next_expected = date.fromisoformat(anchor)
        except Exception:
            return jsonify({'error': 'Invalid next_expected_date (use YYYY-MM-DD)'}), 400
    else:
        next_expected = date.today() + timedelta(days=cadence_nominal_days(data['cadence']))

    recurring = RecurringExpense(
        user_id=int(user_id),
        merchant_name=merchant_name,
        # Use the same normalization detection uses, so a typed name has a chance
        # of matching future transactions by key.
        merchant_key=normalize_merchant(merchant_name),
        category=data['category'],
        expected_amount=amount,
        cadence=data['cadence'],
        confirmed_by_user=True,  # User confirmed by creating it manually
        status='active',
        next_expected_date=next_expected
    )
    db.session.add(recurring)
    db.session.commit()

    return jsonify(recurring.to_dict()), 201


@recurring_bp.route('/from-transactions', methods=['POST'])
@jwt_required()
def create_from_transactions():
    """Create a confirmed recurring series seeded from 1–3 real past transactions.
    Storing the exact Plaid description + merchant_entity_id from those picks means
    future syncs can match new charges reliably.
    Body: {transaction_ids:[...], category?, name?, cadence?, expected_amount?}"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    ids = data.get('transaction_ids') or []
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'transaction_ids (1–3) required'}), 400
    if len(ids) > 3:
        return jsonify({'error': 'Select at most 3 transactions'}), 400

    txns = Transaction.query.filter(
        Transaction.id.in_(ids),
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense'
    ).all()
    if not txns:
        return jsonify({'error': 'No matching expense transactions found'}), 404

    # Don't double-link a transaction that already belongs to a series
    already = {
        o.transaction_id for o in RecurringExpenseOccurrence.query.filter(
            RecurringExpenseOccurrence.transaction_id.in_([t.id for t in txns])).all()
    }
    usable = [t for t in txns if t.id not in already]
    if not usable:
        return jsonify({'error': 'Those transactions are already tracked by a recurring expense'}), 400

    usable.sort(key=lambda t: t.transaction_date)
    latest = usable[-1]
    dates = sorted(t.transaction_date.date() for t in usable)
    amounts = [Decimal(t.amount) for t in usable]

    # Cadence: explicit override, else inferred from the picked dates, else monthly
    cadence = data.get('cadence')
    if cadence:
        if cadence not in RECURRING_CADENCES:
            return jsonify({'error': f'cadence must be one of {", ".join(RECURRING_CADENCES)}'}), 400
    else:
        cadence = (infer_cadence(dates) if len(dates) >= 2 else None) or 'monthly'

    # Entity id only if all picks agree; varying/blank ids fall back to name/date matching
    entity_ids = {t.merchant_entity_id for t in usable if t.merchant_entity_id}
    merchant_entity_id = next(iter(entity_ids)) if len(entity_ids) == 1 else None

    category = data.get('category')
    if not category:
        counts = Counter(t.category for t in usable if t.category)
        category = counts.most_common(1)[0][0] if counts else None

    series = RecurringExpense(
        user_id=int(user_id),
        merchant_name=(data.get('name') or latest.merchant_name or latest.description),
        merchant_key=normalize_merchant(latest.description),
        merchant_entity_id=merchant_entity_id,
        category=category,
        expected_amount=(sum(amounts) / len(amounts)).quantize(Decimal('0.01')),
        cadence=cadence,
        status='active',
        confirmed_by_user=True
    )
    db.session.add(series)
    db.session.flush()
    _attach_occurrences(series, usable)  # sets expected_amount(avg) + next_expected_date

    # Explicit amount override wins over the averaged value
    if data.get('expected_amount') is not None:
        try:
            override = Decimal(str(data['expected_amount']))
        except Exception:
            return jsonify({'error': 'Invalid expected_amount'}), 400
        if override <= 0:
            return jsonify({'error': 'expected_amount must be positive'}), 400
        series.expected_amount = override

    db.session.commit()
    return jsonify(series.to_dict(include_occurrences=True)), 201


@recurring_bp.route('/detect', methods=['POST'])
@jwt_required()
def run_detection():
    """Scan transaction history for recurring charges. Idempotent — safe to
    call on page load."""
    user_id = get_jwt_identity()
    result = detect_recurring(int(user_id))
    return jsonify(result), 200


@recurring_bp.route('', methods=['GET'])
@jwt_required()
def list_recurring():
    """?status=review (unconfirmed candidates) | confirmed | all"""
    user_id = get_jwt_identity()
    status = request.args.get('status', 'all')

    query = RecurringExpense.query.filter_by(user_id=int(user_id))
    if status == 'review':
        query = query.filter_by(status='active', confirmed_by_user=False)
    elif status == 'confirmed':
        query = query.filter_by(status='active', confirmed_by_user=True)

    series = query.order_by(RecurringExpense.next_expected_date.asc().nullslast()).all()
    return jsonify([s.to_dict(include_occurrences=True) for s in series]), 200


@recurring_bp.route('/<int:series_id>/confirm', methods=['POST'])
@jwt_required()
def confirm_recurring(series_id):
    """Yes, this is a real recurring expense (optionally correcting category)."""
    user_id = get_jwt_identity()
    series = RecurringExpense.query.filter_by(id=series_id, user_id=int(user_id)).first()
    if not series:
        return jsonify({'error': 'Recurring expense not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'category' in data:
        series.category = data['category']
    series.confirmed_by_user = True
    series.status = 'active'
    db.session.commit()
    return jsonify(series.to_dict()), 200


@recurring_bp.route('/<int:series_id>/dismiss', methods=['POST'])
@jwt_required()
def dismiss_recurring(series_id):
    """Not actually recurring (e.g. coincidental grocery runs) — hide it and
    don't re-flag these transactions."""
    user_id = get_jwt_identity()
    series = RecurringExpense.query.filter_by(id=series_id, user_id=int(user_id)).first()
    if not series:
        return jsonify({'error': 'Recurring expense not found'}), 404

    series.status = 'dismissed'
    db.session.commit()
    return jsonify(series.to_dict()), 200


@recurring_bp.route('/<int:series_id>', methods=['PUT'])
@jwt_required()
def update_recurring(series_id):
    """Edit category, expected amount, cadence, or mark cancelled_by_user."""
    user_id = get_jwt_identity()
    series = RecurringExpense.query.filter_by(id=series_id, user_id=int(user_id)).first()
    if not series:
        return jsonify({'error': 'Recurring expense not found'}), 404

    data = request.get_json() or {}
    if 'category' in data:
        series.category = data['category']
    if 'expected_amount' in data:
        try:
            amount = Decimal(str(data['expected_amount']))
        except Exception:
            return jsonify({'error': 'Invalid expected_amount'}), 400
        if amount <= 0:
            return jsonify({'error': 'expected_amount must be positive'}), 400
        series.expected_amount = amount
    if 'cadence' in data:
        if data['cadence'] not in RECURRING_CADENCES:
            return jsonify({'error': f'cadence must be one of {", ".join(RECURRING_CADENCES)}'}), 400
        series.cadence = data['cadence']
        if series.occurrences:
            last = max(o.occurred_at for o in series.occurrences)
            series.next_expected_date = last + timedelta(days=cadence_nominal_days(series.cadence))
    if 'status' in data:
        if data['status'] not in ('active', 'cancelled_by_user'):
            return jsonify({'error': 'status must be active or cancelled_by_user'}), 400
        series.status = data['status']

    db.session.commit()
    return jsonify(series.to_dict()), 200


@recurring_bp.route('/summary', methods=['GET'])
@jwt_required()
def recurring_summary():
    """Per-category monthly-equivalent recurring subtotal, for the Budget tab
    badge. Confirmed active series only."""
    user_id = get_jwt_identity()
    series = RecurringExpense.query.filter_by(
        user_id=int(user_id), status='active', confirmed_by_user=True).all()

    by_category = {}
    total = Decimal('0')
    for s in series:
        monthly = s.monthly_equivalent
        total += monthly
        entry = by_category.setdefault(s.category or 'other', {'monthly_total': Decimal('0'), 'count': 0})
        entry['monthly_total'] += monthly
        entry['count'] += 1

    return jsonify({
        'total_monthly': float(total),
        'categories': [
            {'category': category, 'monthly_total': float(v['monthly_total']), 'count': v['count']}
            for category, v in sorted(by_category.items())
        ]
    }), 200
