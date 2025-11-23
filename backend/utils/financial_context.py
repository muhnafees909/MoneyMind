"""
Utility module for gathering user financial context for AI chatbot.
Provides functions to aggregate user's budgets, goals, transactions, and spending data.
"""

from datetime import date
from decimal import Decimal
from sqlalchemy import func, extract
from models.user import db
from models.transaction import Transaction
from models.budget import Budget
from models.goal import FinancialGoal


def get_user_budgets(user_id):
    """
    Get all active budgets for the user with current month progress.

    Returns list of dicts with:
    - category: Budget category
    - budget_amount: Planned budget amount
    - spent_this_month: Actual spending this month
    - progress_percentage: (spent / budget) * 100
    """
    budgets = Budget.query.filter_by(user_id=int(user_id), is_active=True).all()

    budget_list = []
    current_date = date.today()

    for budget in budgets:
        # Get spending for this category this month
        spent = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == int(user_id),
            Transaction.category == budget.category,
            Transaction.transaction_type == 'expense',
            extract('month', Transaction.transaction_date) == current_date.month,
            extract('year', Transaction.transaction_date) == current_date.year
        ).scalar()

        spent_amount = float(spent) if spent else 0.0
        budget_amount = float(budget.amount)
        progress = (spent_amount / budget_amount * 100) if budget_amount > 0 else 0

        budget_list.append({
            'category': budget.category,
            'budget_amount': budget_amount,
            'spent_this_month': spent_amount,
            'progress_percentage': round(progress, 2),
            'is_over_budget': spent_amount > budget_amount
        })

    return budget_list


def get_user_goals(user_id):
    """
    Get active financial goals and recently completed ones.

    Returns list of dicts with:
    - name: Goal name
    - description: Goal description
    - target_amount: Target amount
    - current_amount: Current progress
    - progress_percentage: (current / target) * 100
    - status: 'active' or 'completed'
    - days_until_target: Days until target date (if set)
    """
    goals = FinancialGoal.query.filter_by(user_id=int(user_id)).all()

    goal_list = []
    current_date = date.today()

    for goal in goals:
        target_amount = float(goal.target_amount)
        current_amount = float(goal.current_amount)
        progress = (current_amount / target_amount * 100) if target_amount > 0 else 0

        days_until = None
        if goal.target_date:
            days_until = (goal.target_date - current_date).days

        goal_dict = {
            'name': goal.name,
            'description': goal.description or '',
            'target_amount': target_amount,
            'current_amount': current_amount,
            'progress_percentage': round(progress, 2),
            'status': 'completed' if goal.is_completed else 'active',
            'days_until_target': days_until
        }

        goal_list.append(goal_dict)

    return goal_list


def get_spending_summary(user_id):
    """
    Get spending summary for current month and year-to-date.

    Returns dict with:
    - month_spending: Total spending this month
    - month_income: Total income this month
    - month_net: Income - spending this month
    - ytd_spending: Year-to-date spending
    - ytd_income: Year-to-date income
    - average_monthly_spending: Average monthly spending (all-time)
    """
    current_date = date.today()
    current_year = current_date.year
    current_month = current_date.month

    # Month totals
    month_spending = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense',
        extract('month', Transaction.transaction_date) == current_month,
        extract('year', Transaction.transaction_date) == current_year
    ).scalar()

    month_income = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'income',
        extract('month', Transaction.transaction_date) == current_month,
        extract('year', Transaction.transaction_date) == current_year
    ).scalar()

    # Year-to-date totals
    ytd_spending = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense',
        extract('year', Transaction.transaction_date) == current_year
    ).scalar()

    ytd_income = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'income',
        extract('year', Transaction.transaction_date) == current_year
    ).scalar()

    # Average monthly (all transactions divided by months active)
    all_spending = db.session.query(
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense'
    ).scalar()

    transaction_count = db.session.query(
        func.count(Transaction.id)
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense'
    ).scalar()

    # Estimate months of data (rough: divide by typical transactions per month)
    months_active = max(1, transaction_count // max(1, (transaction_count // 12)))
    average_monthly = float(all_spending) / months_active if all_spending else 0.0

    return {
        'month_spending': float(month_spending) if month_spending else 0.0,
        'month_income': float(month_income) if month_income else 0.0,
        'month_net': (float(month_income) if month_income else 0.0) - (float(month_spending) if month_spending else 0.0),
        'ytd_spending': float(ytd_spending) if ytd_spending else 0.0,
        'ytd_income': float(ytd_income) if ytd_income else 0.0,
        'average_monthly_spending': round(average_monthly, 2)
    }


def get_recent_transactions(user_id, limit=20):
    """
    Get recent transactions for the user.

    Returns list of transaction dicts ordered by date (most recent first).
    Limited to specified number of transactions.
    """
    transactions = Transaction.query.filter_by(
        user_id=int(user_id)
    ).order_by(
        Transaction.transaction_date.desc()
    ).limit(limit).all()

    transaction_list = []
    for tx in transactions:
        transaction_list.append({
            'date': tx.transaction_date.isoformat(),
            'description': tx.description,
            'category': tx.category,
            'amount': float(tx.amount),
            'type': tx.transaction_type,
            'notes': tx.transaction_notes or ''
        })

    return transaction_list


def get_spending_by_category(user_id):
    """
    Get spending breakdown by category for current month.

    Returns list of dicts with:
    - category: Category name
    - amount: Total spending in category this month
    - transaction_count: Number of transactions in category
    """
    current_date = date.today()

    results = db.session.query(
        Transaction.category,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).filter(
        Transaction.user_id == int(user_id),
        Transaction.transaction_type == 'expense',
        extract('month', Transaction.transaction_date) == current_date.month,
        extract('year', Transaction.transaction_date) == current_date.year
    ).group_by(Transaction.category).all()

    category_list = []
    for row in results:
        category_list.append({
            'category': row.category,
            'amount': float(row.total),
            'transaction_count': row.count
        })

    return category_list


def format_context_for_llm(user_id):
    """
    Gather all financial context and format it into a structured
    prompt-friendly format for the LLM.

    Returns dict with all financial data organized for AI consumption.
    """
    try:
        budgets = get_user_budgets(user_id)
    except Exception as e:
        print(f"Error getting budgets: {e}")
        budgets = []

    try:
        goals = get_user_goals(user_id)
    except Exception as e:
        print(f"Error getting goals: {e}")
        goals = []

    try:
        spending_summary = get_spending_summary(user_id)
    except Exception as e:
        print(f"Error getting spending summary: {e}")
        spending_summary = {
            'month_spending': 0.0,
            'month_income': 0.0,
            'month_net': 0.0,
            'ytd_spending': 0.0,
            'ytd_income': 0.0,
            'average_monthly_spending': 0.0
        }

    try:
        recent_transactions = get_recent_transactions(user_id, limit=20)
    except Exception as e:
        print(f"Error getting recent transactions: {e}")
        recent_transactions = []

    try:
        spending_by_category = get_spending_by_category(user_id)
    except Exception as e:
        print(f"Error getting spending by category: {e}")
        spending_by_category = []

    return {
        'budgets': budgets,
        'goals': goals,
        'spending_summary': spending_summary,
        'recent_transactions': recent_transactions,
        'spending_by_category': spending_by_category
    }


def build_context_string(context):
    """
    Convert financial context dict into a readable string for inclusion
    in the LLM system prompt.

    Returns formatted string suitable for inclusion in ChatGPT prompt.
    """
    lines = ["User's Current Financial Context:"]
    lines.append("=" * 50)

    # Spending Summary
    summary = context['spending_summary']
    lines.append("\nSpending Summary (Current Month):")
    lines.append(f"  Income: ${summary['month_income']:.2f}")
    lines.append(f"  Spending: ${summary['month_spending']:.2f}")
    lines.append(f"  Net: ${summary['month_net']:.2f}")
    lines.append(f"  Average Monthly Spending (All-time): ${summary['average_monthly_spending']:.2f}")

    # Spending by Category
    if context['spending_by_category']:
        lines.append("\nSpending by Category (This Month):")
        for cat in context['spending_by_category']:
            lines.append(f"  {cat['category'].title()}: ${cat['amount']:.2f} ({cat['transaction_count']} transactions)")

    # Budgets
    if context['budgets']:
        lines.append("\nActive Budgets:")
        for budget in context['budgets']:
            status = "OVER" if budget['is_over_budget'] else "OK"
            lines.append(
                f"  {budget['category'].title()}: ${budget['budget_amount']:.2f} "
                f"(spent ${budget['spent_this_month']:.2f}, {budget['progress_percentage']:.1f}%) [{status}]"
            )
    else:
        lines.append("\nActive Budgets: None set yet")

    # Goals
    if context['goals']:
        lines.append("\nFinancial Goals:")
        for goal in context['goals']:
            lines.append(
                f"  {goal['name']}: ${goal['current_amount']:.2f} / ${goal['target_amount']:.2f} "
                f"({goal['progress_percentage']:.1f}%) - {goal['status'].upper()}"
            )
            if goal['days_until_target']:
                lines.append(f"    Target date: {goal['days_until_target']} days away")
    else:
        lines.append("\nFinancial Goals: None set yet")

    lines.append("\n" + "=" * 50)

    return "\n".join(lines)
