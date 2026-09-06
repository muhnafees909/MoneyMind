"""
Category override tests: inline recategorization, manual-vs-auto tracking,
survival across Plaid re-syncs, bulk recategorize, and downstream
recalculation (budget progress, spending chart, recurring links).
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

import routes.plaid as plaid_routes
from models.recurring import RecurringExpense, RecurringExpenseOccurrence
from models.transaction import Transaction
from models.user import db, User


def make_plaid_txn(user, category='GENERAL_MERCHANDISE', plaid_id='ptx-1',
                   merchant='Netflix', entity_id='ent-netflix', amount=15.49):
    txn = Transaction(
        user_id=user.id, amount=amount, description=merchant, category=category,
        transaction_type='expense', transaction_date=datetime.utcnow(),
        transaction_notes='', source='plaid', plaid_transaction_id=plaid_id,
        merchant_name=merchant, merchant_entity_id=entity_id
    )
    db.session.add(txn)
    db.session.commit()
    return txn


class TestCategoryOverride:
    def test_change_category_marks_manual(self, client, auth_headers, user):
        txn = make_plaid_txn(user)
        assert txn.category_source == 'auto'

        res = client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                         json={'category': 'ENTERTAINMENT'})
        assert res.status_code == 200
        body = res.get_json()
        assert body['category'] == 'ENTERTAINMENT'
        assert body['category_source'] == 'manual'

    def test_unknown_category_rejected(self, client, auth_headers, user):
        txn = make_plaid_txn(user)
        res = client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                         json={'category': 'NOT_A_CATEGORY'})
        assert res.status_code == 400

    def test_plaid_row_ledger_fields_locked(self, client, auth_headers, user):
        """Bank-synced rows mirror the bank: amount/date/description refused."""
        txn = make_plaid_txn(user, amount=20.00)
        res = client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                         json={'amount': 999})
        assert res.status_code == 400
        assert float(Transaction.query.filter_by(id=txn.id).one().amount) == 20.00

    def test_manual_transaction_still_fully_editable(self, client, auth_headers, user):
        res = client.post('/api/transactions/', headers=auth_headers, json={
            'amount': 12.0, 'description': 'Coffee', 'category': 'FOOD_AND_DRINK',
            'transaction_date': date.today().isoformat()
        })
        assert res.status_code == 201
        created = res.get_json()
        assert created['category_source'] == 'manual'

        res = client.put(f"/api/transactions/{created['id']}", headers=auth_headers,
                         json={'amount': 14.0, 'category': 'ENTERTAINMENT'})
        assert res.status_code == 200
        assert res.get_json()['amount'] == 14.0


class TestResyncRespectsManual:
    def _run_fake_sync(self, monkeypatch, plaid_item, modified_txns):
        response = {'added': [], 'modified': modified_txns, 'removed': [],
                    'has_more': False, 'next_cursor': 'cursor-1'}
        fake_client = SimpleNamespace(
            # accepts the _request_timeout kwarg the real call passes
            transactions_sync=lambda req, **kwargs: SimpleNamespace(to_dict=lambda: response)
        )
        monkeypatch.setattr(plaid_routes, 'get_plaid_client', lambda: fake_client)
        return plaid_routes.perform_transaction_sync(
            plaid_item.user_id, 'access-1', plaid_item=plaid_item)

    def test_resync_keeps_manual_category(self, client, auth_headers, user, account,
                                          monkeypatch, app):
        from models.plaid_item import PlaidItem
        txn = make_plaid_txn(user, category='GENERAL_MERCHANDISE')
        # User corrects the category
        client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                   json={'category': 'ENTERTAINMENT'})

        # Plaid re-sends the transaction as modified, with its own category
        self._run_fake_sync(monkeypatch, PlaidItem.query.one(), [{
            'transaction_id': 'ptx-1', 'amount': 16.49, 'name': 'NETFLIX.COM',
            'personal_finance_category': {'primary': 'GENERAL_SERVICES'},
            'date': date.today(), 'merchant_name': 'Netflix',
            'merchant_entity_id': 'ent-netflix', 'account_id': 'acct-1'
        }])

        fresh = Transaction.query.filter_by(id=txn.id).one()
        assert fresh.category == 'ENTERTAINMENT'          # manual override kept
        assert fresh.category_source == 'manual'
        assert float(fresh.amount) == 16.49               # bank facts still update
        assert fresh.description == 'NETFLIX.COM'

    def test_resync_still_updates_auto_categories(self, client, auth_headers, user,
                                                  account, monkeypatch, app):
        from models.plaid_item import PlaidItem
        txn = make_plaid_txn(user, category='GENERAL_MERCHANDISE')

        self._run_fake_sync(monkeypatch, PlaidItem.query.one(), [{
            'transaction_id': 'ptx-1', 'amount': 15.49, 'name': 'Netflix',
            'personal_finance_category': {'primary': 'ENTERTAINMENT'},
            'date': date.today(), 'merchant_name': 'Netflix',
            'merchant_entity_id': 'ent-netflix', 'account_id': 'acct-1'
        }])

        fresh = Transaction.query.filter_by(id=txn.id).one()
        assert fresh.category == 'ENTERTAINMENT'          # auto rows keep following Plaid
        assert fresh.category_source == 'auto'


class TestBulkRecategorize:
    def test_updates_own_rows_and_marks_manual(self, client, auth_headers, user):
        txns = [make_plaid_txn(user, plaid_id=f'ptx-{i}', category='GENERAL_MERCHANDISE')
                for i in range(3)]

        res = client.post('/api/transactions/recategorize', headers=auth_headers,
                          json={'transaction_ids': [t.id for t in txns],
                                'category': 'ENTERTAINMENT'})
        assert res.status_code == 200
        assert res.get_json()['updated'] == 3
        for t in Transaction.query.filter(Transaction.user_id == user.id).all():
            assert t.category == 'ENTERTAINMENT'
            assert t.category_source == 'manual'

    def test_cannot_touch_other_users_rows(self, client, auth_headers, user):
        other = User(email='other@example.com', first_name='Other')
        other.set_password('password123')
        db.session.add(other)
        db.session.commit()
        theirs = make_plaid_txn(other, plaid_id='ptx-theirs', category='TRAVEL')
        mine = make_plaid_txn(user, plaid_id='ptx-mine', category='TRAVEL')

        res = client.post('/api/transactions/recategorize', headers=auth_headers,
                          json={'transaction_ids': [mine.id, theirs.id],
                                'category': 'FOOD_AND_DRINK'})
        assert res.status_code == 200
        assert res.get_json()['updated'] == 1
        assert Transaction.query.filter_by(id=theirs.id).one().category == 'TRAVEL'

    def test_rejects_bad_payloads(self, client, auth_headers, user):
        for payload in ({}, {'transaction_ids': [], 'category': 'TRAVEL'},
                        {'transaction_ids': ['x'], 'category': 'TRAVEL'},
                        {'transaction_ids': [1], 'category': 'FAKE'}):
            res = client.post('/api/transactions/recategorize',
                              headers=auth_headers, json=payload)
            assert res.status_code == 400


class TestDownstreamRecalculation:
    def test_budget_progress_follows_recategorization(self, client, auth_headers, user):
        res = client.post('/api/budgets', headers=auth_headers,
                          json={'category': 'FOOD_AND_DRINK', 'amount': 100})
        assert res.status_code == 201
        txn = make_plaid_txn(user, category='GENERAL_MERCHANDISE', amount=40.0)

        def food_progress():
            rows = client.get('/api/budgets/progress', headers=auth_headers).get_json()
            return next(r for r in rows if r['category'] == 'FOOD_AND_DRINK')

        assert food_progress()['spent'] == 0  # filed elsewhere → no budget impact

        client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                   json={'category': 'FOOD_AND_DRINK'})

        after = food_progress()
        assert after['spent'] == 40.0          # recalculated immediately
        assert after['remaining'] == 60.0
        assert after['percentage'] == 40.0

    def test_spending_chart_follows_recategorization(self, client, auth_headers, user):
        txn = make_plaid_txn(user, category='GENERAL_MERCHANDISE', amount=25.0)

        def totals():
            rows = client.get('/api/analytics/spending-by-category',
                              headers=auth_headers).get_json()
            return {r['category']: r['total'] for r in rows}

        assert totals() == {'GENERAL_MERCHANDISE': 25.0}

        client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                   json={'category': 'TRAVEL'})
        assert totals() == {'TRAVEL': 25.0}

    def test_recurring_link_survives_recategorization(self, client, auth_headers, user):
        txn = make_plaid_txn(user, category='GENERAL_SERVICES')
        series = RecurringExpense(
            user_id=user.id, merchant_name='Netflix', merchant_key='netflix',
            merchant_entity_id='ent-netflix', category='GENERAL_SERVICES',
            expected_amount=15.49, cadence='monthly', confirmed_by_user=True
        )
        db.session.add(series)
        db.session.flush()
        db.session.add(RecurringExpenseOccurrence(
            recurring_expense_id=series.id, transaction_id=txn.id,
            amount=15.49, occurred_at=date.today()
        ))
        db.session.commit()

        res = client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                         json={'category': 'ENTERTAINMENT'})
        assert res.status_code == 200

        # The occurrence link is untouched — no re-detection needed
        occurrence = RecurringExpenseOccurrence.query.one()
        assert occurrence.transaction_id == txn.id
        assert occurrence.recurring_expense_id == series.id
        # The series keeps its own category label (drives the Budgets subtotal
        # independently of any single transaction's category)
        assert RecurringExpense.query.one().category == 'GENERAL_SERVICES'


class TestCustomCategoryLegacyCollision:
    """A custom category whose slug collides with a legacy alias
    ('Groceries' -> GROCERIES, which LEGACY_CATEGORY_MAPPING maps to
    FOOD_AND_DRINK) must be stored as itself, not silently rewritten to the
    mapped system category. The rewrite made the write look like a no-op: 200
    OK with category_source flipped to 'manual' but the category unchanged.
    """

    def _make_custom(self, user, name):
        from models.category import Category
        slug = name.replace(' ', '_').upper()
        cat = Category(user_id=user.id, value=slug, name=name,
                       color='#e27c4e', icon='tag')
        db.session.add(cat)
        db.session.commit()
        return slug

    @pytest.mark.parametrize('name,collides_with', [
        ('Groceries', 'FOOD_AND_DRINK'),
        ('Dining', 'FOOD_AND_DRINK'),
        ('Education', 'GENERAL_SERVICES'),
        ('Other', 'GENERAL_SERVICES'),
        ('Utilities', 'RENT_AND_UTILITIES'),
    ])
    def test_colliding_custom_category_is_stored_verbatim(
            self, client, auth_headers, user, name, collides_with):
        slug = self._make_custom(user, name)
        txn = make_plaid_txn(user, category=collides_with)

        res = client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                         json={'category': slug})
        assert res.status_code == 200
        assert res.get_json()['category'] == slug

        fresh = Transaction.query.filter_by(id=txn.id).one()
        assert fresh.category == slug
        assert fresh.category_source == 'manual'

    def test_bulk_recategorize_honours_colliding_custom_category(
            self, client, auth_headers, user):
        slug = self._make_custom(user, 'Groceries')
        txns = [make_plaid_txn(user, plaid_id=f'bulk-{i}', category='FOOD_AND_DRINK')
                for i in range(3)]

        res = client.post('/api/transactions/recategorize', headers=auth_headers,
                          json={'transaction_ids': [t.id for t in txns],
                                'category': slug})
        assert res.status_code == 200
        assert res.get_json()['category'] == slug
        for t in Transaction.query.filter_by(user_id=user.id).all():
            assert t.category == slug

    def test_legacy_lowercase_values_still_migrate(self, client, auth_headers, user):
        """The legacy mapping still applies to values that are NOT assignable
        categories — that is the case it was written for."""
        txn = make_plaid_txn(user, category='TRAVEL')
        res = client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                         json={'category': 'groceries'})
        assert res.status_code == 200
        assert res.get_json()['category'] == 'FOOD_AND_DRINK'

    def test_unknown_category_still_rejected(self, client, auth_headers, user):
        txn = make_plaid_txn(user)
        res = client.put(f'/api/transactions/{txn.id}', headers=auth_headers,
                         json={'category': 'NOPE_NOT_REAL'})
        assert res.status_code == 400
