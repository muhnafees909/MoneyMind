from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.goal import FinancialGoal
from datetime import datetime, date

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('', methods=['GET'])
@jwt_required()
def get_goals():
    """Get all goals for the current user"""
    user_id = get_jwt_identity()
    goals = FinancialGoal.query.filter_by(user_id=int(user_id)).order_by(
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
    
    # Create goal
    goal = FinancialGoal(
        user_id=int(user_id),
        name=data['name'],
        description=data.get('description', ''),
        target_amount=data['target_amount'],
        current_amount=data.get('current_amount', 0),
        target_date=target_date
    )
    
    db.session.add(goal)
    db.session.commit()
    
    return jsonify(goal.to_dict()), 201

@goals_bp.route('/<int:goal_id>', methods=['PUT'])
@jwt_required()
def update_goal(goal_id):
    """Update a goal"""
    user_id = get_jwt_identity()
    goal = FinancialGoal.query.filter_by(id=goal_id, user_id=int(user_id)).first()
    
    if not goal:
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
        goal.current_amount = data['current_amount']
        # Check if goal is completed
        if goal.current_amount >= goal.target_amount and not goal.is_completed:
            goal.is_completed = True
            goal.completed_at = datetime.combine(date.today(), datetime.min.time())
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
    
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    
    data = request.get_json()
    amount = data.get('amount')
    
    if not amount or amount <= 0:
        return jsonify({'error': 'Valid amount required'}), 400
    
    # Add to current amount
    goal.current_amount += amount
    
    # Check if goal is completed
    if goal.current_amount >= goal.target_amount and not goal.is_completed:
        goal.is_completed = True
        goal.completed_at = datetime.combine(date.today(), datetime.min.time())
    
    db.session.commit()
    
    return jsonify(goal.to_dict()), 200

@goals_bp.route('/<int:goal_id>', methods=['DELETE'])
@jwt_required()
def delete_goal(goal_id):
    """Delete a goal"""
    user_id = get_jwt_identity()
    goal = FinancialGoal.query.filter_by(id=goal_id, user_id=int(user_id)).first()
    
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    
    db.session.delete(goal)
    db.session.commit()
    
    return jsonify({'message': 'Goal deleted'}), 200