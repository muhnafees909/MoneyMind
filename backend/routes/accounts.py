"""
Linked-accounts management: view every synced Plaid account/card and set a
custom nickname per account. The nickname is stored separately from the raw
Plaid name (models.plaid_account) and surfaces app-wide via display_name.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.plaid_account import PlaidAccount

accounts_bp = Blueprint('accounts', __name__)

# Keep nicknames sane — this is a label, not free-form storage
MAX_NICKNAME_LEN = 60


@accounts_bp.route('', methods=['GET'])
@jwt_required()
def list_accounts():
    """All of the user's linked accounts/cards, with balances and envelope
    eligibility. Ordered by institution then display name for a stable list."""
    user_id = int(get_jwt_identity())
    accounts = PlaidAccount.query.filter_by(user_id=user_id).all()
    # Sort in Python so nickname (display_name) participates in ordering
    accounts.sort(key=lambda a: (
        (a.plaid_item.institution_name or '').lower() if a.plaid_item else '',
        a.display_name.lower()
    ))
    return jsonify([a.to_dict() for a in accounts]), 200


@accounts_bp.route('/<int:account_id>', methods=['PATCH'])
@jwt_required()
def rename_account(account_id):
    """Set or clear an account's nickname.
    Body: {"nickname": "Main Checking"}  — empty/whitespace/null clears it,
    falling display back to the raw Plaid name."""
    user_id = int(get_jwt_identity())
    account = PlaidAccount.query.filter_by(id=account_id, user_id=user_id).first()
    if not account:
        return jsonify({'error': 'Account not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'nickname' not in data:
        return jsonify({'error': 'nickname field is required'}), 400

    raw = data.get('nickname')
    if raw is None:
        account.nickname = None
    else:
        if not isinstance(raw, str):
            return jsonify({'error': 'nickname must be a string'}), 400
        trimmed = raw.strip()
        if len(trimmed) > MAX_NICKNAME_LEN:
            return jsonify({'error': f'Nickname must be {MAX_NICKNAME_LEN} characters or fewer'}), 400
        # Empty string clears the nickname (revert to Plaid name)
        account.nickname = trimmed or None

    db.session.commit()
    return jsonify(account.to_dict()), 200
