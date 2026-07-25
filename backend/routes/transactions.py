from decimal import Decimal, InvalidOperation
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.transaction import Transaction
from datetime import datetime
from utils.categories import normalize_legacy_category, is_valid_category
from utils.recurring import detect_recurring

transactions_bp = Blueprint("transaction", __name__)

# Amount bounds. The DB column is NUMERIC(10, 2) — it can physically store up to
# 99,999,999.99. We cap well below that at $10M: more than enough for any real
# personal transaction (a house, a car, a down payment) while staying clear of
# the column's ceiling so a valid amount can never overflow it.
MAX_AMOUNT = Decimal('10000000')   # $10,000,000.00
MIN_AMOUNT = Decimal('0.01')


def validate_amount(value):
    """Return (Decimal amount, None) if valid, else (None, error message)."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, 'Amount must be a number.'
    if amount.is_nan() or amount.is_infinite():
        return None, 'Amount must be a valid number.'
    if amount < MIN_AMOUNT:
        return None, 'Amount must be greater than zero.'
    if amount > MAX_AMOUNT:
        return None, f'Amount is too large — it must be at most ${MAX_AMOUNT:,.0f}.'
    return amount, None


def _rerun_recurring_detection(user_id):
    """Manually entered charges feed recurring detection the same way synced
    ones do (the Plaid sync runs detection after every import). Detection is
    idempotent; a failure here must never break the transaction write."""
    try:
        detect_recurring(int(user_id))
    except Exception as e:
        db.session.rollback()
        print(f"Recurring detection after transaction write failed: {e}")

@transactions_bp.route('/', methods=['GET'], endpoint='get_all')
@jwt_required()
def get_transaction():
    user_id = get_jwt_identity()
    transactions = Transaction.query.filter_by(user_id=int(user_id)).order_by(Transaction.transaction_date.desc()).all()
    return jsonify([t.to_dict() for t in transactions]), 200
    
@transactions_bp.route('/', methods=['POST'], endpoint='create')
@jwt_required()
def create_transaction():
    user_id = get_jwt_identity()
    data = request.get_json()

    required_fields =  ['amount', 'description', 'category', 'transaction_date']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    # Validate amount range (guards the NUMERIC(10,2) column from overflow)
    amount, amount_error = validate_amount(data['amount'])
    if amount_error:
        return jsonify({'error': amount_error}), 400

    # Normalize legacy lowercase values, then confirm it's a category the user
    # can actually use (system default or one of their custom categories).
    category = normalize_legacy_category(data.get('category', ''))
    if not is_valid_category(user_id, category):
        return jsonify({'error': 'Unknown category.'}), 400

    transaction = Transaction(
        user_id = int(user_id),
        amount = amount,
        category = category,
        description = data['description'],
        transaction_type=data.get('transaction_type', 'expense'),
        transaction_date=datetime.fromisoformat(data['transaction_date']).date(),
        transaction_notes=data.get('transaction_notes', ''),  # Use .get() for optional fields
        category_source='manual',  # the user picked this category themselves
    )

    db.session.add(transaction)
    db.session.commit()

    # A new manual expense may complete a recurring pattern (e.g. 3rd rent
    # payment) — run detection so the suggestion appears right away
    if transaction.transaction_type == 'expense':
        _rerun_recurring_detection(user_id)

    return jsonify(transaction.to_dict()), 201

@transactions_bp.route('/<int:transaction_id>', methods=['PUT'], endpoint='update')
@jwt_required()
def update_transaction(transaction_id):
    user_id = get_jwt_identity()
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=int(user_id)).first()

    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404

    data = request.get_json()

    # Bank-synced rows mirror the bank's record: amount/date/description stay
    # read-only. Category (and notes) are the user's to correct.
    if transaction.source == 'plaid':
        locked = {'amount', 'description', 'transaction_type', 'transaction_date'}
        attempted = locked.intersection(data.keys())
        if attempted:
            return jsonify({
                'error': 'Bank-synced transactions mirror your bank record — only '
                         'the category and notes can be changed.'
            }), 400

    if 'amount' in data:
        amount, amount_error = validate_amount(data['amount'])
        if amount_error:
            return jsonify({'error': amount_error}), 400
        transaction.amount = amount
    if 'category' in data:
        new_category = normalize_legacy_category(data['category'])
        if not is_valid_category(user_id, new_category):
            return jsonify({'error': 'Unknown category.'}), 400
        if new_category != transaction.category:
            transaction.category = new_category
        # User set it deliberately either way — re-sync must not undo this
        transaction.category_source = 'manual'
    if 'description' in data:
        transaction.description = data['description']
    if 'transaction_type' in data:
        transaction.transaction_type = data['transaction_type']
    if 'transaction_date' in data:
        transaction.transaction_date = datetime.fromisoformat(data['transaction_date']).date()
    if 'transaction_notes' in data:
        transaction.transaction_notes = data['transaction_notes']

    db.session.commit()

    # Amount/date/description edits can create or break a recurring pattern
    if (transaction.transaction_type == 'expense'
            and any(k in data for k in ('amount', 'transaction_date', 'description'))):
        _rerun_recurring_detection(user_id)

    return jsonify(transaction.to_dict()), 200


NOTES_MAX_LEN = 255  # matches the transaction_notes column width


@transactions_bp.route('/<int:transaction_id>/notes', methods=['PATCH'], endpoint='update_notes')
@jwt_required()
def update_notes(transaction_id):
    """Set/edit/clear the user's note on ANY transaction — manual or
    Plaid-synced. Notes are a user field, independent of the bank record, so
    there is no source restriction here (unlike amount/date, which are locked
    for synced rows). Body: {"transaction_notes": "..."} (empty string clears)."""
    user_id = get_jwt_identity()
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=int(user_id)).first()
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'transaction_notes' not in data:
        return jsonify({'error': 'transaction_notes field is required'}), 400

    note = data.get('transaction_notes')
    if note is None:
        note = ''
    if not isinstance(note, str):
        return jsonify({'error': 'transaction_notes must be a string'}), 400

    note = note.strip()
    if len(note) > NOTES_MAX_LEN:
        return jsonify({'error': f'Note must be {NOTES_MAX_LEN} characters or fewer'}), 400

    transaction.transaction_notes = note
    db.session.commit()
    return jsonify(transaction.to_dict()), 200


@transactions_bp.route('/recategorize', methods=['POST'], endpoint='recategorize')
@jwt_required()
def bulk_recategorize():
    """
    Set the same category on several transactions at once (the "Plaid keeps
    filing this merchant wrong" fix). All rows are marked as manual overrides
    so future syncs leave them alone.

    Request JSON: {"transaction_ids": [1, 2, 3], "category": "FOOD_AND_DRINK"}
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}

    ids = data.get('transaction_ids')
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
        return jsonify({'error': '"transaction_ids" must be a non-empty list of ids.'}), 400
    if len(ids) > 500:
        return jsonify({'error': 'Too many transactions at once (max 500).'}), 400

    category = normalize_legacy_category(data.get('category', ''))
    if not is_valid_category(user_id, category):
        return jsonify({'error': 'Unknown category.'}), 400

    # Only rows the user owns; ids belonging to others are silently skipped
    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.id.in_(ids)
    ).all()

    for transaction in transactions:
        transaction.category = category
        transaction.category_source = 'manual'
    db.session.commit()

    return jsonify({
        'updated': len(transactions),
        'category': category,
        'transactions': [t.to_dict() for t in transactions]
    }), 200

@transactions_bp.route('/<int:transaction_id>', methods=['DELETE'], endpoint='delete')
@jwt_required()
def delete_transaction(transaction_id):
    user_id = get_jwt_identity()
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=int(user_id)).first()

    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404

    # Clean up rows that reference this transaction (recurring occurrences,
    # income events, envelope allocations) — same cleanup the Plaid sync does
    # for retracted transactions. Without this, deleting a transaction that
    # belongs to a recurring series violates the FK constraint.
    from routes.plaid import _delete_removed_transaction
    _delete_removed_transaction(transaction)
    db.session.commit()

    return jsonify({'message': 'Transaction deleted'}), 200
