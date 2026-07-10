from datetime import datetime, timedelta

from models.user import db
from utils.financial_context import format_context_for_llm, build_context_string
from tests.conftest import make_goal
from tests.test_recurring import monthly_series
from utils.recurring import detect_recurring
from models.recurring import RecurringExpense


class TestChatContext:
    def test_context_includes_envelopes_and_recurring(self, client, auth_headers, user, account):
        # envelope: goal linked to the HYSA with $200 allocated
        goal = make_goal(user, name='Hajj', linked_account_id=account.id)
        client.post('/api/envelopes/allocations', headers=auth_headers,
                    json={'goal_id': goal.id, 'amount': 200})

        # recurring: confirmed monthly subscription
        monthly_series(user, months=3)
        detect_recurring(user.id)
        series = RecurringExpense.query.one()
        series.confirmed_by_user = True
        db.session.commit()

        context = format_context_for_llm(user.id)
        assert context['envelope_accounts'][0]['allocated_total'] == 200.0
        assert context['envelope_accounts'][0]['unallocated_cash'] == 800.0
        assert context['recurring']['total_monthly'] == 15.49
        assert context['recurring']['pending_review_count'] == 0

        text = build_context_string(context)
        assert 'ENVELOPES' in text
        assert 'Hajj: $200.00 of $2,000.00 target' in text
        assert 'RECURRING EXPENSES ($15.49/month total)' in text
        assert 'Netflix.com' in text

    def test_context_safe_with_no_envelope_or_recurring_data(self, app, user):
        context = format_context_for_llm(user.id)
        assert context['envelope_accounts'] == []
        assert context['recurring']['series'] == []
        # should not raise or add empty sections
        text = build_context_string(context)
        assert 'ENVELOPES' not in text
        assert 'RECURRING EXPENSES' not in text
