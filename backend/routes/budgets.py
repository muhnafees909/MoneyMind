from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.budget import Budget
from models.transaction import Transaction
from sqlalchemy import func, extract
from datetime import datetime

budgets_bp = Blueprint('budgets', __name__)

@budgets_bp.route('', methods=['GET'])
@jwt_required()
def get_budgets():
    """Get all active budgets for the current user"""
    user_id = get_jwt_identity()
    budgets = Budget.query.filter_by(user_id=int(user_id), is_active=True).all()
    return jsonify([b.to_dict() for b in budgets]), 200

@budgets_bp.route('', methods=['POST'])
@jwt_required()
def create_budget():
    """Create a new recurring budget"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    if not data.get('category') or not data.get('amount'):
        return jsonify({'error': 'Category and amount are required'}), 400
    
    # Check if budget already exists for this category
    existing = Budget.query.filter_by(
        user_id=int(user_id),
        category=data['category']
    ).first()
    
    if existing:
        return jsonify({'error': 'Budget already exists for this category. Use update instead.'}), 400
    
    # Create budget
    budget = Budget(
        user_id=int(user_id),
        category=data['category'],
        amount=data['amount'],
        is_active=True
    )
    
    db.session.add(budget)
    db.session.commit()
    
    return jsonify(budget.to_dict()), 201

@budgets_bp.route('/<int:budget_id>', methods=['PUT'])
@jwt_required()
def update_budget(budget_id):
    """Update a budget amount"""
    user_id = get_jwt_identity()
    budget = Budget.query.filter_by(id=budget_id, user_id=int(user_id)).first()
    
    if not budget:
        return jsonify({'error': 'Budget not found'}), 404
    
    data = request.get_json()
    
    # Update amount
    if 'amount' in data:
        budget.amount = data['amount']
    
    # Update active status
    if 'is_active' in data:
        budget.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify(budget.to_dict()), 200

@budgets_bp.route('/<int:budget_id>', methods=['DELETE'])
@jwt_required()
def delete_budget(budget_id):
    """Delete a budget"""
    user_id = get_jwt_identity()
    budget = Budget.query.filter_by(id=budget_id, user_id=int(user_id)).first()
    
    if not budget:
        return jsonify({'error': 'Budget not found'}), 404
    
    db.session.delete(budget)
    db.session.commit()
    
    return jsonify({'message': 'Budget deleted'}), 200

@budgets_bp.route('/progress', methods=['GET'])
@jwt_required()
def get_budget_progress():
    """Get budget vs actual spending for current month (or specified month)"""
    user_id = get_jwt_identity()
    
    # Get current month/year or from query params
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    
    # Get all active budgets (recurring, so no month/year filter)
    budgets = Budget.query.filter_by(
        user_id=int(user_id),
        is_active=True
    ).all()
    
    # Get actual spending by category for the specified month
    actual_spending = db.session.query(
        Transaction.category,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense',
        extract('month', Transaction.transaction_date) == month,
        extract('year', Transaction.transaction_date) == year
    ).group_by(Transaction.category).all()
    
    # Create a dictionary of actual spending
    spending_dict = {row.category: float(row.total) for row in actual_spending}
    
    # Combine budgets with actual spending
    progress = []
    for budget in budgets:
        actual = spending_dict.get(budget.category, 0)
        progress.append({
            'budget_id': budget.id,
            'category': budget.category,
            'budgeted': float(budget.amount),
            'spent': actual,
            'remaining': float(budget.amount) - actual,
            'percentage': (actual / float(budget.amount) * 100) if budget.amount > 0 else 0,
            'month': month,
            'year': year
        })
    
    return jsonify(progress), 200