from decimal import Decimal
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.goal import FinancialGoal
from models.plaid_account import PlaidAccount
from routes.envelopes import apply_allocation, envelope_balance
from datetime import datetime, date

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('', methods=['GET'])
@jwt_required()
def get_goals():
    """Get all non-deleted goals for the current user"""
    user_id = get_jwt_identity()
    goals = FinancialGoal.query.filter_by(user_id=int(user_id), deleted_at=None).order_by(
        FinancialGoal.is_completed.asc(),
        FinancialGoal.created_at.desc()
    ).all()
    return jsonify([g.to_dict() for g in goals]), 200

@goals_bp.route('', methods=['POST'])
@jwt_required()
def create_goal():
    """Create a new financial goal"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    if not data.get('name') or not data.get('target_amount'):
        return jsonify({'error': 'Name and target amount are required'}), 400
    
    # Parse target date if provided - FIX TIMEZONE ISSUE
    target_date = None
    if data.get('target_date'):
        try:
            # Extract just the date part (YYYY-MM-DD) to avoid timezone issues
            date_str = data['target_date']
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, AttributeError) as e:
            return jsonify({'error': f'Invalid date format. Use YYYY-MM-DD. Error: {str(e)}'}), 400
    
    # Optional envelope link: validate the account belongs to this user
    linked_account_id = None
    if data.get('linked_account_id'):
        account = PlaidAccount.query.filter_by(
            id=data['linked_account_id'], user_id=int(user_id)).first()
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        linked_account_id = account.id

    # Create goal
    goal = FinancialGoal(
        user_id=int(user_id),
        name=data['name'],
        description=data.get('description', ''),
        target_amount=data['target_amount'],
        current_amount=data.get('current_amount', 0),
        target_date=target_date,
        linked_account_id=linked_account_id,
        priority_order=data.get('priority_order')
    )

    db.session.add(goal)
    db.session.flush()  # need goal.id to seed the ledger

    # If created already holding money, seed the envelope ledger to match
    if linked_account_id and Decimal(goal.current_amount) != 0:
        seed = Decimal(goal.current_amount)
        goal.current_amount = 0  # apply_allocation adds it back
        apply_allocation(goal, seed, 'correction', note='Initial balance when goal created')

    db.session.commit()

    return jsonify(goal.to_dict()), 201

@goals_bp.route('/<int:goal_id>', methods=['PUT'])
@jwt_required()
def update_goal(goal_id):
    """Update a goal"""
    user_id = get_jwt_identity()
    goal = FinancialGoal.query.filter_by(id=goal_id, user_id=int(user_id)).first()

    if not goal or goal.deleted_at:
        return jsonify({'error': 'Goal not found'}), 404
    
    data = request.get_json()
    
    # Update fields
    if 'name' in data:
        goal.name = data['name']
    if 'description' in data:
        goal.description = data['description']
    if 'target_amount' in data:
        goal.target_amount = data['target_amount']
    if 'current_amount' in data:
        new_amount = Decimal(str(data['current_amount']))
        if goal.linked_account_id:
            # Envelope goal: record the change in the ledger instead of silently
            # overwriting the counter, so reconciliation stays truthful
            delta = new_amount - Decimal(goal.current_amount)
            if delta != 0:
                apply_allocation(goal, delta, 'correction', note='Manual edit of goal amount')
        else:
            goal.current_amount = new_amount
            # Check if goal is completed
            if goal.current_amount >= goal.target_amount and not goal.is_completed:
                goal.is_completed = True
                goal.completed_at = datetime.combine(date.today(), datetime.min.time())

    # Envelope linking: attach/detach this goal to a real Plaid account
    if 'linked_account_id' in data:
        if data['linked_account_id']:
            account = PlaidAccount.query.filter_by(
                id=data['linked_account_id'], user_id=int(user_id)).first()
            if not account:
                return jsonify({'error': 'Account not found'}), 404
            newly_linked = goal.linked_account_id != account.id
            goal.linked_account_id = account.id
            # Seed the ledger so it matches money already saved toward this goal
            if newly_linked and Decimal(goal.current_amount) != envelope_balance(goal.id):
                seed = Decimal(goal.current_amount) - envelope_balance(goal.id)
                goal.current_amount = Decimal(goal.current_amount) - seed  # apply_allocation adds it back
                apply_allocation(goal, seed, 'correction', note='Initial balance when linked to account')
        else:
            goal.linked_account_id = None
    if 'priority_order' in data:
        goal.priority_order = data['priority_order']
    if 'target_date' in data:
        if data['target_date']:
            date_str = data['target_date']
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            goal.target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            goal.target_date = None
    
    db.session.commit()
    
    return jsonify(goal.to_dict()), 200

@goals_bp.route('/<int:goal_id>/add-progress', methods=['POST'])
@jwt_required()
def add_progress(goal_id):
    """Add progress to a goal (add money toward goal)"""
    user_id = get_jwt_identity()
    goal = FinancialGoal.query.filter_by(id=goal_id, user_id=int(user_id)).first()

    if not goal or goal.deleted_at:
        return jsonify({'error': 'Goal not found'}), 404
    
    data = request.get_json()
    amount = data.get('amount')

    if not amount or amount <= 0:
        return jsonify({'error': 'Valid amount required'}), 400

    amount = Decimal(str(amount))  # Decimal + float raises TypeError on Numeric columns

    if goal.linked_account_id:
        # Envelope goal: progress goes through the allocation ledger
        apply_allocation(goal, amount, 'manual', note='Added via goal progress')
    else:
        goal.current_amount = Decimal(goal.current_amount) + amount

        # Check if goal is completed
        if goal.current_amount >= goal.target_amount and not goal.is_completed:
            goal.is_completed = True
            goal.completed_at = datetime.combine(date.today(), datetime.min.time())

    db.session.commit()
    
    return jsonify(goal.to_dict()), 200

@goals_bp.route('/<int:goal_id>', methods=['DELETE'])
@jwt_required()
def delete_goal(goal_id):
    """Soft-delete a goal. User can restore it within 30 days."""
    user_id = get_jwt_identity()
    goal = FinancialGoal.query.filter_by(id=goal_id, user_id=int(user_id)).first()

    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    if goal.deleted_at:
        return jsonify({'error': 'Goal already deleted'}), 409

    goal.deleted_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'message': 'Goal deleted. You can restore it within 30 days.',
        'goal': goal.to_dict()
    }), 200


@goals_bp.route('/<int:goal_id>/restore', methods=['POST'])
@jwt_required()
def restore_goal(goal_id):
    """Restore a soft-deleted goal."""
    user_id = get_jwt_identity()
    goal = FinancialGoal.query.filter_by(id=goal_id, user_id=int(user_id)).first()

    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    if not goal.deleted_at:
        return jsonify({'error': 'Goal is not deleted'}), 400

    goal.deleted_at = None
    db.session.commit()

    return jsonify({
        'message': 'Goal restored',
        'goal': goal.to_dict()
    }), 200