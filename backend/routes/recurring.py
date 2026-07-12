from decimal import Decimal
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.recurring import RecurringExpense, RECURRING_CADENCES
from utils.recurring import detect_recurring, cadence_nominal_days
from datetime import timedelta

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

    # Normalize merchant name (use description if provided, else default)
    merchant_name = data.get('description', 'Manual Entry')
    merchant_key = merchant_name.lower().strip()  # Simple normalization

    # Create recurring expense record
    recurring = RecurringExpense(
        user_id=int(user_id),
        merchant_name=merchant_name,
        merchant_key=merchant_key,
        category=data['category'],
        expected_amount=amount,
        cadence=data['cadence'],
        confirmed_by_user=True,  # User confirmed by creating it manually
        status='active',
        next_expected_date=None  # No historical occurrences to base this on
    )
    db.session.add(recurring)
    db.session.commit()

    return jsonify(recurring.to_dict()), 201


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
