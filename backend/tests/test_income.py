from datetime import datetime
from decimal import Decimal

import pytest

from models.user import db
from models.transaction import Transaction
from models.envelope import AllocationRule, EnvelopeAllocation
from models.income_event import IncomeEvent
from utils.income import is_likely_income, compute_suggested_split
from tests.conftest import make_goal


def make_txn(user, amount=2000, description='ACME CORP PAYROLL', category='INCOME',
             transaction_type='income', source='plaid', account=None, plaid_id=None):
    txn = Transaction(
        user_id=user.id, amount=amount, description=description,
        category=category, transaction_type=transaction_type,
        transaction_date=datetime(2026, 7, 1), transaction_notes='',
        source=source, plaid_transaction_id=plaid_id,
        plaid_account_id=account.id if account else None
    )
    db.session.add(txn)
    db.session.commit()
    return txn


class TestIncomeHeuristic:
    def test_plaid_income_category_detected(self, app, user):
        assert is_likely_income(make_txn(user, category='INCOME', description='ACH CREDIT')) is True

    def test_payroll_keyword_detected(self, app, user):
        txn = make_txn(user, category='other', description='DIRECT DEP - ACME LLC')
        assert is_likely_income(txn) is True

    def test_small_deposits_ignored(self, app, user):
        assert is_likely_income(make_txn(user, amount=25, category='INCOME')) is False

    def test_expense_and_manual_ignored(self, app, user):
        assert is_likely_income(make_txn(user, transaction_type='expense')) is False
        assert is_likely_income(make_txn(user, source='manual')) is False

    def test_unknown_one_off_deposit_ignored(self, app, user):
        txn = make_txn(user, category='TRANSFER_IN', description='ZELLE FROM RANDOM')
        assert is_likely_income(txn) is False

    def test_recurring_payer_detected(self, app, user):
        for i in range(2):
            make_txn(user, category='TRANSFER_IN', description='MYSTERY EMPLOYER',
                     plaid_id=f'p-{i}')
        third = make_txn(user, category='TRANSFER_IN', description='MYSTERY EMPLOYER',
                         plaid_id='p-3')
        assert is_likely_income(third) is True


class TestSuggestedSplit:
    def add_rule(self, user, goal, priority, rule_type, fixed=None, pct=None, active=True):
        rule = AllocationRule(user_id=user.id, goal_id=goal.id, priority_order=priority,
                              allocation_type=rule_type, fixed_amount=fixed,
                              percentage=pct, is_active=active)
        db.session.add(rule)
        db.session.commit()
        return rule

    def test_waterfall_fixed_then_percentage_then_remainder(self, app, user, account):
        emergency = make_goal(user, name='Emergency', target=10000, linked_account_id=account.id)
        roth = make_goal(user, name='Roth IRA', target=7000, linked_account_id=account.id)
        hajj = make_goal(user, name='Hajj', target=8000, linked_account_id=account.id)
        self.add_rule(user, emergency, 1, 'fixed_amount', fixed=500)
        self.add_rule(user, roth, 2, 'percentage', pct=20)
        self.add_rule(user, hajj, 3, 'remainder')

        split, remainder = compute_suggested_split(user.id, Decimal('2000'))
        amounts = {row['goal_name']: row['amount'] for row in split}
        assert amounts['Emergency'] == 500.0
        assert amounts['Roth IRA'] == 400.0       # 20% of gross 2000
        assert amounts['Hajj'] == 1100.0          # remainder
        assert remainder == 0

    def test_fixed_rule_capped_by_goal_headroom_and_deposit(self, app, user, account):
        nearly_done = make_goal(user, name='Nearly', target=1000, current=950,
                                linked_account_id=account.id)
        self.add_rule(user, nearly_done, 1, 'fixed_amount', fixed=400)

        split, remainder = compute_suggested_split(user.id, Decimal('2000'))
        assert split[0]['amount'] == 50.0  # capped at what the goal still needs
        assert remainder == Decimal('1950')

    def test_goals_without_rules_included_at_zero(self, app, user, account):
        make_goal(user, name='NoRule', linked_account_id=account.id)
        split, remainder = compute_suggested_split(user.id, Decimal('1000'))
        assert split == [{'goal_id': split[0]['goal_id'], 'goal_name': 'NoRule',
                          'amount': 0.0, 'rule_type': None}]
        assert remainder == Decimal('1000')

    def test_inactive_rules_skipped(self, app, user, account):
        goal = make_goal(user, name='Paused', linked_account_id=account.id)
        self.add_rule(user, goal, 1, 'fixed_amount', fixed=500, active=False)
        split, _ = compute_suggested_split(user.id, Decimal('1000'))
        assert split[0]['rule_type'] is None
        assert split[0]['amount'] == 0.0


class TestIncomeEventEndpoints:
    def make_event(self, client, headers, user, account, amount=2000):
        txn = make_txn(user, amount=amount, account=account, plaid_id='evt-txn')
        res = client.post('/api/envelopes/income-events/scan', headers=headers)
        assert res.status_code == 200
        event = IncomeEvent.query.filter_by(transaction_id=txn.id).first()
        assert event is not None
        return event

    def test_scan_is_idempotent(self, client, auth_headers, user, account):
        make_txn(user, account=account, plaid_id='t1')
        first = client.post('/api/envelopes/income-events/scan', headers=auth_headers)
        second = client.post('/api/envelopes/income-events/scan', headers=auth_headers)
        assert first.get_json()['created'] == 1
        assert second.get_json()['created'] == 0

    def test_pending_events_include_suggested_split(self, client, auth_headers, user, account):
        goal = make_goal(user, name='Emergency', linked_account_id=account.id)
        db.session.add(AllocationRule(user_id=user.id, goal_id=goal.id, priority_order=1,
                                      allocation_type='fixed_amount', fixed_amount=500))
        db.session.commit()
        self.make_event(client, auth_headers, user, account)

        res = client.get('/api/envelopes/income-events', headers=auth_headers)
        events = res.get_json()
        assert len(events) == 1
        assert events[0]['suggested_split'][0]['amount'] == 500.0
        assert events[0]['unallocated_remainder'] == 1500.0

    def test_confirm_writes_paycheck_split_allocations(self, client, auth_headers, user, account):
        hajj = make_goal(user, name='Hajj', linked_account_id=account.id)
        marriage = make_goal(user, name='Marriage', target=3500, linked_account_id=account.id)
        event = self.make_event(client, auth_headers, user, account)

        res = client.post(f'/api/envelopes/income-events/{event.id}/confirm',
                          headers=auth_headers,
                          json={'allocations': [
                              {'goal_id': hajj.id, 'amount': 800},
                              {'goal_id': marriage.id, 'amount': 700},
                              {'goal_id': hajj.id, 'amount': 0}  # blank rows skipped
                          ]})
        assert res.status_code == 200
        assert res.get_json()['allocated_total'] == 1500.0

        rows = EnvelopeAllocation.query.filter_by(source_type='paycheck_split').all()
        assert len(rows) == 2
        assert all(r.source_transaction_id == event.transaction_id for r in rows)
        assert event.status == 'confirmed'

        # can't confirm twice
        res = client.post(f'/api/envelopes/income-events/{event.id}/confirm',
                          headers=auth_headers,
                          json={'allocations': [{'goal_id': hajj.id, 'amount': 10}]})
        assert res.status_code == 400

    def test_confirm_rejects_overallocation(self, client, auth_headers, user, account):
        goal = make_goal(user, name='Hajj', target=99999, linked_account_id=account.id)
        event = self.make_event(client, auth_headers, user, account, amount=1000)
        res = client.post(f'/api/envelopes/income-events/{event.id}/confirm',
                          headers=auth_headers,
                          json={'allocations': [{'goal_id': goal.id, 'amount': 1500}]})
        assert res.status_code == 400
        assert 'exceeds' in res.get_json()['error']

    def test_dismiss(self, client, auth_headers, user, account):
        event = self.make_event(client, auth_headers, user, account)
        res = client.post(f'/api/envelopes/income-events/{event.id}/dismiss',
                          headers=auth_headers)
        assert res.status_code == 200
        assert res.get_json()['status'] == 'dismissed'
        # dismissed events no longer show as pending
        pending = client.get('/api/envelopes/income-events', headers=auth_headers).get_json()
        assert pending == []

    def test_sync_creates_income_event(self, client, auth_headers, user, account, monkeypatch):
        """End-to-end: a payroll deposit arriving via Plaid sync creates a pending event."""
        from routes import plaid as plaid_module

        class FakeResponse:
            def to_dict(self):
                return {'added': [{
                    'transaction_id': 'sync-1',
                    'amount': -2500.00,  # negative = money in, per Plaid convention
                    'name': 'ACME CORP PAYROLL',
                    'date': datetime(2026, 7, 2),
                    'account_id': account.plaid_account_id,
                    'personal_finance_category': {'primary': 'INCOME'},
                    'merchant_name': 'ACME'
                }]}

        class FakeClient:
            def transactions_sync(self, req, **kwargs):
                return FakeResponse()

        monkeypatch.setattr(plaid_module, 'get_plaid_client', lambda: FakeClient())

        result = plaid_module.perform_transaction_sync(user.id, 'fake-token')
        assert result['saved'] == 1

        event = IncomeEvent.query.first()
        assert event is not None
        assert event.status == 'pending'
        assert float(event.amount) == 2500.00
        assert event.plaid_account_id == account.id
        txn = Transaction.query.filter_by(plaid_transaction_id='sync-1').first()
        assert txn.plaid_account_id == account.id
