import json
from models.transaction import Transaction
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from sqlalchemy import func, extract
from datetime import datetime, timedelta

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route('/spending-by-category', methods=["GET"])
@jwt_required()
def spending_by_category():
    """Get total spending grouped by category"""
    user_id = get_jwt_identity()

    results = db.session.query(
        Transaction.category,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense'
    ).group_by(Transaction.category).all()

    category_totals = [
        {"category": row.category, "total": float(row.total)}
        for row in results 
    ]

    return jsonify(category_totals), 200

@analytics_bp.route('/monthly-spending', methods=['GET'])
@jwt_required()
def monthly_spending():
    """Get total spending by month for the current year"""
    user_id = get_jwt_identity()
    current_year = datetime.now().year

    results = db.session.query(
        extract('month', Transaction.transaction_date).label('month'),
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense',
        extract('year', Transaction.transaction_date) == current_year
    ).group_by('month').order_by('month').all()

    # Month names
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    # Format response with month names
    monthly_totals = [
        {
            'month': int(row.month),
            'month_name': month_names[int(row.month) - 1],  # -1 because list is 0-indexed
            'total': float(row.total)
        }
        for row in results
    ]
    
    return jsonify(monthly_totals), 200

@analytics_bp.route('/spending-summary', methods=['GET'])
@jwt_required()
def spending_summary():
    """Get overall spending statistics"""
    user_id = get_jwt_identity()

    total_expenses = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == "expense"
    ).scalar() or 0

    total_income = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == "income"
    ).scalar() or 0

    transaction_count = Transaction.query.filter_by(
        user_id = int(user_id)
    ).count()

    return jsonify({
        'total_expenses': float(total_expenses),
        'total_income': float(total_income),
        'net': float(total_income - total_expenses),
        'transaction_count': transaction_count
    }), 200

