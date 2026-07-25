import json
from models.transaction import Transaction
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from utils.categories import category_lookup, display_name_from, color_from

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

    lookup = category_lookup(user_id)
    category_totals = [
        {
            "category": row.category,
            "display_name": display_name_from(row.category, lookup),
            "color": color_from(row.category, lookup),
            "total": float(row.total)
        }
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

@analytics_bp.route('/spending-by-category/monthly', methods=['GET'])
@jwt_required()
def spending_by_category_monthly():
    """Get spending by category for current month"""
    user_id = get_jwt_identity()

    # Get current month start/end
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1).date()
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1).date()
    else:
        month_end = datetime(now.year, now.month + 1, 1).date()

    results = db.session.query(
        Transaction.category,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense',
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date < month_end
    ).group_by(Transaction.category).all()

    lookup = category_lookup(user_id)
    category_totals = [
        {
            "category": row.category,
            "display_name": display_name_from(row.category, lookup),
            "color": color_from(row.category, lookup),
            "total": float(row.total)
        }
        for row in results
    ]

    return jsonify(category_totals), 200

@analytics_bp.route('/spending-summary/monthly', methods=['GET'])
@jwt_required()
def spending_summary_monthly():
    """Get spending summary for current month"""
    user_id = get_jwt_identity()

    # Get current month start/end
    now = datetime.now()
    month_start = datetime(now.year, now.month, 1).date()
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1).date()
    else:
        month_end = datetime(now.year, now.month + 1, 1).date()

    # Month expenses
    month_expenses = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date < month_end
    ).scalar() or 0

    # Month income
    month_income = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == "income",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date < month_end
    ).scalar() or 0

    # Month transaction count
    month_count = Transaction.query.filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date < month_end
    ).count()

    return jsonify({
        'month_expenses': float(month_expenses),
        'month_income': float(month_income),
        'month_net': float(month_income - month_expenses),
        'month_count': month_count
    }), 200

