from datetime import date, datetime, timedelta

from models.user import db
from utils.financial_context import (format_context_for_llm, build_context_string,
                                     get_monthly_spending_history)
from tests.conftest import make_goal
from tests.test_recurring import monthly_series, make_expense
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
        assert 'RECURRING EXPENSES — confirmed baseline bills: $15.49/month total' in text
        assert 'Netflix.com' in text

    def test_context_safe_with_no_envelope_or_recurring_data(self, app, user):
        context = format_context_for_llm(user.id)
        assert context['envelope_accounts'] == []
        assert context['recurring']['series'] == []
        # should not raise or add empty sections
        text = build_context_string(context)
        assert 'ENVELOPES' not in text
        assert 'RECURRING EXPENSES' not in text
        assert 'TOTAL SPENDING BY MONTH' not in text


def _prior_month(months_back):
    """First day of the month `months_back` full months before the current one."""
    d = date.today().replace(day=1)
    for _ in range(months_back):
        d = (d - timedelta(days=1)).replace(day=1)
    return d


class TestSpendingHistory:
    def test_covers_last_full_months_and_excludes_current(self, app, user):
        for months_back, amount in ((3, 300.0), (2, 200.0), (1, 100.0)):
            m = _prior_month(months_back)
            make_expense(user, f'Rent {months_back}', amount, datetime(m.year, m.month, 5))
        # current-month spending must not affect the completed-month average
        today = date.today()
        make_expense(user, 'This month', 999.0, datetime(today.year, today.month, 1))

        history = get_monthly_spending_history(user.id)
        assert [m['total'] for m in history['months']] == [300.0, 200.0, 100.0]
        assert history['months'][0]['label'] == _prior_month(3).strftime('%B %Y')
        assert history['average'] == 200.0

    def test_context_string_labels_history_and_average(self, app, user):
        m = _prior_month(1)
        make_expense(user, 'Rent', 1200.0, datetime(m.year, m.month, 5))

        context = format_context_for_llm(user.id)
        text = build_context_string(context)
        assert 'TOTAL SPENDING BY MONTH (last 1 completed month(s))' in text
        assert f"{m.strftime('%B %Y')}: $1,200.00" in text
        assert f"Average TOTAL monthly spending ({m.strftime('%B %Y')}): $1,200.00" in text


class TestChatRouteHistory:
    def _fake_send(self, captured):
        def fake(user_id, message, history=None):
            captured['message'] = message
            captured['history'] = history
            return {'response': 'ok', 'context_used': {}, 'error': None}
        return fake

    def test_history_forwarded_to_llm(self, client, auth_headers, monkeypatch):
        captured = {}
        monkeypatch.setattr('routes.chat.send_message', self._fake_send(captured))
        resp = client.post('/api/chat/message', headers=auth_headers, json={
            'message': 'Stable, one income',
            'history': [
                {'role': 'user', 'content': 'How big should my emergency fund be?'},
                {'role': 'assistant', 'content': 'Is your income stable?'}
            ]
        })
        assert resp.status_code == 200
        assert captured['message'] == 'Stable, one income'
        assert [m['role'] for m in captured['history']] == ['user', 'assistant']

    def test_malformed_history_rejected(self, client, auth_headers, monkeypatch):
        captured = {}
        monkeypatch.setattr('routes.chat.send_message', self._fake_send(captured))
        for bad in ('not-a-list',
                    [{'role': 'system', 'content': 'x'}],
                    [{'role': 'user'}],
                    [{'role': 'user', 'content': 'x' * 5001}]):
            resp = client.post('/api/chat/message', headers=auth_headers,
                               json={'message': 'hi', 'history': bad})
            assert resp.status_code == 400
        assert captured == {}
