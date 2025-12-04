from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db, User
from models.financial import Transaction, Budget, Goal, Category, Income
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import os
import openai

chat_bp = Blueprint('chat', __name__)

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')


def get_improved_system_prompt():
    """
    Returns the improved, less restrictive system prompt that:
    - Explicitly allows legitimate financial questions
    - Only refuses non-finance topics
    - Encourages using user data
    - Promotes comprehensive, actionable advice
    """
    return """You are a personal financial advisor for the MoneyMind app.

You MUST answer questions about:
- User's spending, budgets, income, savings, and financial health
- Spending summaries, analysis, and patterns
- Budget performance and recommendations
- Financial goals and progress tracking
- General finance topics (investing, saving strategies, debt management, budgeting tips)
- Financial summaries like "How am I doing?" or "Give me a summary"
- Spending concerns like "Should I be worried?" or "Am I overspending?"
- Comparisons and trends (month-over-month, category analysis)

You should REFUSE ONLY:
- Completely non-finance topics (sports, weather, entertainment, cooking, politics, etc.)
- Personal advice outside of finance
- Requests to perform actions you cannot do (you can only provide advice, not execute transactions)

When answering:
- ALWAYS use the user's actual financial data provided below
- Be specific with numbers and percentages
- Give actionable, concrete recommendations
- Be encouraging but realistic and honest
- Reference specific transactions, budgets, or goals when relevant
- Provide context by comparing to averages or past performance
- Calculate projections when helpful
- Highlight both positive achievements and areas for improvement

Remember: Your role is to help users understand and improve their finances. Be confident, helpful, and data-driven.

The user's financial data is provided below in the USER FINANCIAL SNAPSHOT section. Use this data to give personalized, specific advice."""


def gather_user_financial_context(user_id):
    """
    Gathers comprehensive financial context for the user including:
    - Monthly spending summary
    - Spending by category
    - Recent transactions
    - Budget status and alerts
    - Financial goals progress
    - Spending trends and projections
    - Income information

    Returns a beautifully formatted context string with emojis and clear sections
    """
    now = datetime.utcnow()
    current_month = now.month
    current_year = now.year

    # Calculate days in current month and days remaining
    if current_month == 12:
        next_month = datetime(current_year + 1, 1, 1)
    else:
        next_month = datetime(current_year, current_month + 1, 1)

    days_in_month = (next_month - datetime(current_year, current_month, 1)).days
    days_remaining = (next_month - now).days
    days_elapsed = days_in_month - days_remaining

    # Get user's income
    income_sources = Income.query.filter_by(user_id=user_id).all()
    monthly_income = sum([inc.amount for inc in income_sources if inc.frequency == 'monthly'])

    # Get current month transactions
    month_start = datetime(current_year, current_month, 1)
    current_month_transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.date >= month_start,
        Transaction.date < next_month
    ).all()

    # Calculate spending summary
    total_expenses = sum([t.amount for t in current_month_transactions if t.transaction_type == 'expense'])
    total_income_this_month = sum([t.amount for t in current_month_transactions if t.transaction_type == 'income'])
    net_this_month = total_income_this_month - total_expenses

    # Get previous month for comparison
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year

    prev_month_start = datetime(prev_year, prev_month, 1)
    prev_month_end = datetime(current_year, current_month, 1)

    prev_month_transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.date >= prev_month_start,
        Transaction.date < prev_month_end,
        Transaction.transaction_type == 'expense'
    ).all()

    prev_month_total = sum([t.amount for t in prev_month_transactions])

    # Calculate spending trend
    if prev_month_total > 0:
        spending_change_pct = ((total_expenses - prev_month_total) / prev_month_total) * 100
        trend_indicator = "📈" if spending_change_pct > 0 else "📉"
        trend_text = f"{trend_indicator} {abs(spending_change_pct):.1f}% {'higher' if spending_change_pct > 0 else 'lower'} than last month"
    else:
        trend_text = "No previous month data for comparison"

    # Calculate projection
    if days_elapsed > 0:
        daily_avg = total_expenses / days_elapsed
        projected_month_end = daily_avg * days_in_month
    else:
        projected_month_end = 0

    # Get spending by category
    category_spending = db.session.query(
        Category.name,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= month_start,
        Transaction.date < next_month,
        Transaction.transaction_type == 'expense'
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    # Get budgets for current month
    budgets = Budget.query.filter_by(
        user_id=user_id,
        month=current_month,
        year=current_year
    ).all()

    # Calculate budget status
    budget_alerts = []
    budget_summary = []

    for budget in budgets:
        category_total = sum([
            t.amount for t in current_month_transactions
            if t.category_id == budget.category_id and t.transaction_type == 'expense'
        ])

        percent_used = (category_total / budget.amount * 100) if budget.amount > 0 else 0
        remaining = budget.amount - category_total

        if category_total > budget.amount:
            status = "⚠️ OVER BUDGET"
            alert = f"  - {budget.category.name}: OVER BUDGET by ${abs(remaining):.2f}"
            budget_alerts.append(alert)
        elif percent_used > 90:
            status = "⚠️ NEAR LIMIT"
            alert = f"  - {budget.category.name}: {percent_used:.1f}% used (${remaining:.2f} remaining)"
            budget_alerts.append(alert)
        else:
            status = "✅ UNDER BUDGET"

        budget_summary.append({
            'category': budget.category.name,
            'status': status,
            'spent': category_total,
            'budget': budget.amount,
            'remaining': remaining,
            'percent': percent_used
        })

    # Get recent transactions (last 10)
    recent_transactions = Transaction.query.filter_by(
        user_id=user_id
    ).order_by(Transaction.date.desc()).limit(10).all()

    # Get financial goals
    goals = Goal.query.filter_by(user_id=user_id, completed=False).all()
    goal_insights = []

    for goal in goals:
        remaining_amount = goal.target_amount - goal.current_amount
        progress_pct = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0

        if goal.deadline:
            days_until_deadline = (goal.deadline - now.date()).days
            if days_until_deadline > 0:
                daily_needed = remaining_amount / days_until_deadline
                urgency = "⚠️ URGENT" if days_until_deadline <= 30 else ""
                goal_insights.append({
                    'name': goal.name,
                    'progress': progress_pct,
                    'current': goal.current_amount,
                    'target': goal.target_amount,
                    'days_left': days_until_deadline,
                    'daily_needed': daily_needed,
                    'urgency': urgency
                })
            else:
                goal_insights.append({
                    'name': goal.name,
                    'progress': progress_pct,
                    'current': goal.current_amount,
                    'target': goal.target_amount,
                    'overdue': True
                })
        else:
            goal_insights.append({
                'name': goal.name,
                'progress': progress_pct,
                'current': goal.current_amount,
                'target': goal.target_amount,
                'no_deadline': True
            })

    # Format the context string
    context = f"""{'='*60}
USER FINANCIAL SNAPSHOT ({datetime.now().strftime('%B %Y')})
{'='*60}

📊 MONTHLY SUMMARY
  Income: ${monthly_income:,.2f}
  Spending: ${total_expenses:,.2f}
  Net: ${net_this_month:,.2f}
  Days remaining: {days_remaining} of {days_in_month}

📈 SPENDING TRENDS
  - Current month: ${total_expenses:,.2f}
  - Last month: ${prev_month_total:,.2f}
  - {trend_text}
  - Projected month-end total: ${projected_month_end:,.2f}
"""

    # Add alerts if any
    if budget_alerts:
        context += f"\n⚠️ IMMEDIATE ALERTS\n"
        context += "\n".join(budget_alerts) + "\n"

    # Add spending breakdown
    if category_spending:
        context += f"\n💰 SPENDING BREAKDOWN\n"
        for idx, (category, total, count) in enumerate(category_spending[:5], 1):
            percent_of_total = (total / total_expenses * 100) if total_expenses > 0 else 0
            context += f"  {idx}. {category}: ${total:,.2f} ({count} transactions) - {percent_of_total:.1f}% of spending\n"

    # Add budget status
    if budget_summary:
        context += f"\n📈 BUDGET STATUS\n"
        for b in budget_summary:
            context += f"  {b['status']} {b['category']}: ${b['spent']:.2f} / ${b['budget']:.2f} ({b['percent']:.1f}% used)\n"
            if b['remaining'] > 0:
                context += f"      → ${b['remaining']:.2f} remaining\n"

    # Add goals
    if goal_insights:
        context += f"\n🎯 FINANCIAL GOALS\n"
        for g in goal_insights:
            context += f"  - {g['name']}: ${g['current']:,.2f} / ${g['target']:,.2f} ({g['progress']:.1f}%)\n"
            if 'daily_needed' in g:
                context += f"      → Need ${g['daily_needed']:.2f}/day for {g['days_left']} days {g['urgency']}\n"
            elif g.get('overdue'):
                context += f"      → ⚠️ DEADLINE PASSED\n"

    # Add recent transactions
    if recent_transactions:
        context += f"\n💳 RECENT ACTIVITY (Last 10 Transactions)\n"
        for t in recent_transactions:
            category_name = t.category.name if t.category else "Uncategorized"
            sign = "-" if t.transaction_type == 'expense' else "+"
            context += f"  - {t.date.strftime('%m/%d')}: {t.description} - {sign}${t.amount:,.2f} ({category_name})\n"

    context += f"\n{'='*60}\n"

    return context


@chat_bp.route('/message', methods=['POST'])
@jwt_required()
def chat_message():
    """
    Main chat endpoint for AI financial advisor

    Expected request body:
    {
        "message": "User's question or message"
    }

    Returns:
    {
        "response": "AI's response",
        "success": true
    }
    """
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get user's message
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Message is required'}), 400

        # Gather financial context
        financial_context = gather_user_financial_context(current_user_id)

        # Get improved system prompt
        system_prompt = get_improved_system_prompt()

        # Combine system prompt with financial context
        full_system_prompt = f"{system_prompt}\n\n{financial_context}"

        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Using GPT-4o-mini as specified
            messages=[
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=800
        )

        # Extract AI response
        ai_response = response.choices[0].message.content

        return jsonify({
            'response': ai_response,
            'success': True
        }), 200

    except openai.error.AuthenticationError:
        return jsonify({
            'error': 'OpenAI API key is invalid or missing',
            'success': False
        }), 500

    except openai.error.RateLimitError:
        return jsonify({
            'error': 'OpenAI API rate limit exceeded. Please try again later.',
            'success': False
        }), 429

    except openai.error.OpenAIError as e:
        return jsonify({
            'error': f'OpenAI API error: {str(e)}',
            'success': False
        }), 500

    except Exception as e:
        return jsonify({
            'error': f'Internal server error: {str(e)}',
            'success': False
        }), 500


@chat_bp.route('/context', methods=['GET'])
@jwt_required()
def get_context():
    """
    Endpoint to view the financial context that would be sent to the AI
    Useful for debugging and understanding what data the AI sees
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        context = gather_user_financial_context(current_user_id)

        return jsonify({
            'context': context,
            'success': True
        }), 200

    except Exception as e:
        return jsonify({
            'error': f'Internal server error: {str(e)}',
            'success': False
        }), 500
