"""
Utility module for gathering user financial context for AI chatbot.
Provides functions to aggregate user's budgets, goals, transactions, and spending data.
"""

from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import func, extract
from models.user import db
from models.transaction import Transaction
from models.budget import Budget
from models.goal import FinancialGoal
from models.plaid_account import PlaidAccount
from models.recurring import RecurringExpense
import calendar


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


def get_spending_trends(user_id):
    """
    Calculate spending trends and month-end projections.

    Returns dict with:
    - highest_category: Category with most spending this month
    - highest_amount: Amount in highest category
    - month_growth_percent: Change from last month (positive = higher spending)
    - days_remaining: Days left in current month
    - projected_month_total: Projected month-end total based on current pace
    - last_month_spending: Total spending last month
    - budget_alerts: List of budgets that are over-budget
    """
    try:
        current_date = date.today()

        # 1. Find highest spending category this month
        categories = get_spending_by_category(user_id)
        highest_category = max(categories, key=lambda x: x['amount']) if categories else None

        # 2. Get current month spending
        summary = get_spending_summary(user_id)
        current_month_spending = summary['month_spending']

        # 3. Get last month spending for comparison
        # Calculate first and last day of last month
        first_day_this_month = date(current_date.year, current_date.month, 1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = date(last_day_last_month.year, last_day_last_month.month, 1)

        last_month_spending = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == int(user_id),
            Transaction.transaction_type == 'expense',
            Transaction.transaction_date >= first_day_last_month,
            Transaction.transaction_date < first_day_this_month
        ).scalar() or 0
        last_month_spending = float(last_month_spending)

        # 4. Calculate month-over-month growth percentage
        if last_month_spending > 0:
            month_growth = ((current_month_spending - last_month_spending) / last_month_spending) * 100
        else:
            month_growth = 0

        # 5. Calculate days remaining in month
        days_in_month = calendar.monthrange(current_date.year, current_date.month)[1]
        days_elapsed = current_date.day
        days_remaining = days_in_month - days_elapsed

        # 6. Project month-end total
        if days_elapsed > 0:
            daily_average = current_month_spending / days_elapsed
            projected_total = daily_average * days_in_month
        else:
            projected_total = 0

        # 7. Get budget alerts (categories that are over budget)
        budgets = get_user_budgets(user_id)
        alerts = [b for b in budgets if b['is_over_budget']]

        return {
            'highest_category': highest_category['category'] if highest_category else None,
            'highest_amount': highest_category['amount'] if highest_category else 0,
            'month_growth_percent': round(month_growth, 1),
            'days_remaining': days_remaining,
            'days_in_month': days_in_month,
            'projected_month_total': round(projected_total, 2),
            'last_month_spending': round(last_month_spending, 2),
            'budget_alerts': alerts,
            'current_spending': round(current_month_spending, 2)
        }
    except Exception as e:
        print(f"Error calculating spending trends: {str(e)}")
        return {
            'highest_category': None,
            'highest_amount': 0,
            'month_growth_percent': 0,
            'days_remaining': 0,
            'days_in_month': 0,
            'projected_month_total': 0,
            'last_month_spending': 0,
            'budget_alerts': [],
            'current_spending': 0
        }


def get_envelope_context(user_id):
    """
    Per linked account: bank balance vs envelope balances vs unallocated cash.
    Mirrors the Envelopes reconciliation screen so the advisor can answer
    "how much do I actually have for Hajj?" style questions.
    """
    from routes.envelopes import envelope_balance  # local import to avoid circularity

    accounts = PlaidAccount.query.filter_by(user_id=int(user_id)).all()
    result = []
    for account in accounts:
        goals = FinancialGoal.query.filter_by(
            user_id=int(user_id), linked_account_id=account.id).all()
        envelopes = []
        allocated = Decimal('0')
        for goal in goals:
            balance = envelope_balance(goal.id)
            allocated += balance
            envelopes.append({
                'goal_name': goal.name,
                'envelope_balance': float(balance),
                'target_amount': float(goal.target_amount)
            })
        actual = Decimal(account.current_balance) if account.current_balance is not None else None
        result.append({
            'account_name': account.name,
            'institution': account.plaid_item.institution_name if account.plaid_item else None,
            'actual_balance': float(actual) if actual is not None else None,
            'allocated_total': float(allocated),
            'unallocated_cash': float(actual - allocated) if actual is not None else None,
            'envelopes': envelopes
        })
    return result


def get_recurring_context(user_id):
    """
    Confirmed recurring expenses (with price-creep flags) plus how many
    candidates are waiting in the review queue.
    """
    confirmed = RecurringExpense.query.filter_by(
        user_id=int(user_id), status='active', confirmed_by_user=True).all()
    pending_review = RecurringExpense.query.filter_by(
        user_id=int(user_id), status='active', confirmed_by_user=False).count()

    series_list = []
    total_monthly = Decimal('0')
    for series in confirmed:
        total_monthly += series.monthly_equivalent
        series_list.append({
            'merchant': series.merchant_name,
            'category': series.category,
            'expected_amount': float(series.expected_amount),
            'cadence': series.cadence,
            'monthly_equivalent': float(series.monthly_equivalent),
            'next_expected_date': series.next_expected_date.isoformat() if series.next_expected_date else None,
            'price_creep': series.price_creep
        })

    return {
        'series': series_list,
        'total_monthly': float(total_monthly),
        'pending_review_count': pending_review
    }


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

    try:
        spending_trends = get_spending_trends(user_id)
    except Exception as e:
        print(f"Error getting spending trends: {e}")
        spending_trends = {
            'highest_category': None,
            'highest_amount': 0,
            'month_growth_percent': 0,
            'days_remaining': 0,
            'days_in_month': 0,
            'projected_month_total': 0,
            'last_month_spending': 0,
            'budget_alerts': [],
            'current_spending': 0
        }

    try:
        envelope_accounts = get_envelope_context(user_id)
    except Exception as e:
        print(f"Error getting envelope context: {e}")
        envelope_accounts = []

    try:
        recurring = get_recurring_context(user_id)
    except Exception as e:
        print(f"Error getting recurring context: {e}")
        recurring = {'series': [], 'total_monthly': 0.0, 'pending_review_count': 0}

    return {
        'budgets': budgets,
        'goals': goals,
        'spending_summary': spending_summary,
        'recent_transactions': recent_transactions,
        'spending_by_category': spending_by_category,
        'spending_trends': spending_trends,
        'envelope_accounts': envelope_accounts,
        'recurring': recurring
    }


def build_context_string(context):
    """
    Convert financial context dict into a readable, scannable string for inclusion
    in the LLM system prompt. Uses clear sections and formatting for readability.

    Returns formatted string suitable for inclusion in ChatGPT prompt.
    """
    lines = []

    # Get data with safe defaults
    summary = context.get('spending_summary', {})
    transactions = context.get('recent_transactions', [])
    budgets = context.get('budgets', [])
    goals = context.get('goals', [])
    categories = context.get('spending_by_category', [])
    trends = context.get('spending_trends', {})

    current_date = date.today()
    month_name = current_date.strftime("%B %Y")

    # Header
    lines.append(f"USER FINANCIAL SNAPSHOT ({month_name})")
    lines.append("=" * 60)

    # 1. MONTHLY SUMMARY SECTION
    lines.append("\n📊 MONTHLY SUMMARY")
    lines.append(f"  Income: ${summary.get('month_income', 0):,.2f}")
    lines.append(f"  Spending: ${summary.get('month_spending', 0):,.2f}")
    lines.append(f"  Net: ${summary.get('month_net', 0):,.2f}")
    lines.append(f"  Days remaining: {trends.get('days_remaining', 0)} of {trends.get('days_in_month', 30)}")

    # 2. ALERTS SECTION (if any budgets are over)
    alerts = trends.get('budget_alerts', [])
    if alerts:
        lines.append("\n⚠️ IMMEDIATE ALERTS")
        for alert in alerts:
            over_by = alert['spent_this_month'] - alert['budget_amount']
            lines.append(f"  🔴 {alert['category'].title()}: OVER BUDGET by ${over_by:,.2f}")
        lines.append(f"  📈 Projected month-end: ${trends.get('projected_month_total', 0):,.2f}")

    # 3. SPENDING BREAKDOWN SECTION
    if categories:
        lines.append("\n💰 SPENDING BREAKDOWN (This Month)")
        for cat in sorted(categories, key=lambda x: x['amount'], reverse=True):
            lines.append(f"  {cat['category'].title()}: ${cat['amount']:,.2f} ({cat['transaction_count']} tx)")

        highest_cat = trends.get('highest_category')
        if highest_cat:
            growth = trends.get('month_growth_percent', 0)
            lines.append(f"\n  Top category: {highest_cat.title()} at ${trends.get('highest_amount', 0):,.2f}")
            lines.append(f"  Spending trend: {growth:+.1f}% vs last month")

    # 4. BUDGET STATUS SECTION
    if budgets:
        lines.append("\n📈 BUDGET STATUS")
        for budget in budgets:
            status_emoji = "✅" if not budget['is_over_budget'] else "🔴"
            remaining = budget['budget_amount'] - budget['spent_this_month']
            status_text = f"${remaining:,.2f} left" if remaining >= 0 else f"${abs(remaining):,.2f} over"
            lines.append(
                f"  {status_emoji} {budget['category'].title()}: "
                f"${budget['spent_this_month']:,.2f}/${budget['budget_amount']:,.2f} ({status_text})"
            )
    else:
        lines.append("\n📈 BUDGET STATUS: No budgets set yet")

    # 5. FINANCIAL GOALS SECTION
    if goals:
        lines.append("\n🎯 FINANCIAL GOALS")
        for goal in goals:
            status_emoji = "✅" if goal['status'] == 'completed' else "📍"
            remaining = goal['target_amount'] - goal['current_amount']
            lines.append(
                f"  {status_emoji} {goal['name']}: "
                f"${goal['current_amount']:,.2f}/${goal['target_amount']:,.2f} ({goal['progress_percentage']:.1f}%)"
            )

            if goal['days_until_target'] and goal['days_until_target'] > 0 and remaining > 0:
                daily_need = remaining / goal['days_until_target']
                lines.append(f"     → Need ${daily_need:,.2f}/day for {goal['days_until_target']} more days")
    else:
        lines.append("\n🎯 FINANCIAL GOALS: None set yet")

    # 6. ENVELOPES SECTION (virtual sub-allocations of real accounts)
    envelope_accounts = context.get('envelope_accounts', [])
    if envelope_accounts:
        lines.append("\n✉️ ENVELOPES (how linked bank accounts are divided across goals)")
        for account in envelope_accounts:
            balance_text = f"${account['actual_balance']:,.2f}" if account['actual_balance'] is not None else "unknown"
            lines.append(f"  🏦 {account['account_name']}: balance {balance_text}, "
                         f"allocated ${account['allocated_total']:,.2f}")
            for envelope in account['envelopes']:
                lines.append(f"     ✉️ {envelope['goal_name']}: ${envelope['envelope_balance']:,.2f} "
                             f"of ${envelope['target_amount']:,.2f} target")
            if account['unallocated_cash'] is not None:
                flag = " ⚠️ OVER-ALLOCATED" if account['unallocated_cash'] < 0 else ""
                lines.append(f"     💵 Unallocated: ${account['unallocated_cash']:,.2f}{flag}")

    # 7. RECURRING EXPENSES SECTION
    recurring = context.get('recurring', {})
    if recurring.get('series'):
        lines.append(f"\n🔁 RECURRING EXPENSES (${recurring['total_monthly']:,.2f}/month total)")
        for series in recurring['series']:
            creep = series.get('price_creep')
            creep_text = f" 🔴 PRICE UP {creep['increase_pct']}% (was ${creep['previous_average']:,.2f})" if creep else ""
            next_date = f", next ~{series['next_expected_date']}" if series['next_expected_date'] else ""
            lines.append(f"  🔁 {series['merchant']}: ${series['expected_amount']:,.2f} {series['cadence']}"
                         f" (${series['monthly_equivalent']:,.2f}/mo){next_date}{creep_text}")
    if recurring.get('pending_review_count'):
        lines.append(f"  📥 {recurring['pending_review_count']} possible recurring charge(s) awaiting review")

    # 8. RECENT TRANSACTIONS SECTION
    if transactions:
        lines.append("\n💳 RECENT TRANSACTIONS (Last 10)")
        for tx in transactions[:10]:
            tx_emoji = "💸" if tx['type'] == 'expense' else "💰"
            tx_date = tx['date'][:10] if 'T' in tx['date'] else tx['date']  # Extract date part if ISO format
            lines.append(f"  {tx_emoji} {tx_date}: {tx['description']} - ${tx['amount']:,.2f} ({tx['category'].title()})")

    lines.append("\n" + "=" * 60)

    return "\n".join(lines)
