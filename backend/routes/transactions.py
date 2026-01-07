from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.transaction import Transaction
from datetime import datetime
from utils.categories import normalize_legacy_category

transactions_bp = Blueprint("transaction", __name__)

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

    # Normalize category to Plaid format
    category = normalize_legacy_category(data.get('category', ''))

    transaction = Transaction(
        user_id = int(user_id),
        amount = data['amount'],
        category = category,
        description = data['description'],
        transaction_type=data.get('transaction_type', 'expense'),
        transaction_date=datetime.fromisoformat(data['transaction_date']).date(),
        transaction_notes=data.get('transaction_notes', ''),  # Use .get() for optional fields
    )

    db.session.add(transaction)
    db.session.commit()

    return jsonify(transaction.to_dict()), 201

@transactions_bp.route('/<int:transaction_id>', methods=['PUT'], endpoint='update')
@jwt_required()
def update_transaction(transaction_id):
    user_id = get_jwt_identity()
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=int(user_id)).first()

    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    data = request.get_json()

    if 'amount' in data:
        transaction.amount = data['amount']
    if 'category' in data:
        transaction.category = normalize_legacy_category(data['category'])
    if 'description' in data:
        transaction.description = data['description']
    if 'transaction_type' in data:
        transaction.transaction_type = data['transaction_type']
    if 'transaction_date' in data:
        transaction.transaction_date = datetime.fromisoformat(data['transaction_date']).date()
    if 'transaction_notes' in data:
        transaction.transaction_notes = data['transaction_notes']
    
    db.session.commit()

    return jsonify(transaction.to_dict()), 200

@transactions_bp.route('/<int:transaction_id>', methods=['DELETE'], endpoint='delete')
@jwt_required()
def delete_transaction(transaction_id):
    user_id = get_jwt_identity()
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=int(user_id)).first()

    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    db.session.delete(transaction)
    db.session.commit()

    return jsonify({'message': 'Transaction deleted'}), 200
