"""
Tests for recurring-expense matching improvements:
- Capturing Plaid merchant_name / merchant_entity_id
- POST /from-transactions (select-from-history seeding)
- Priority matching of future charges to a seeded series:
    1. merchant_entity_id
    2. exact normalized name
    3. amount + date-window (varying description text)
    4. fuzzy name + amount + date-window
"""
from datetime import datetime, timedelta
from decimal import Decimal

from models.user import db
from models.transaction import Transaction
from models.recurring import RecurringExpense, RecurringExpenseOccurrence
from utils.recurring import detect_recurring, normalize_merchant


def make_expense(user, description, amount, when, category='RENT_AND_UTILITIES',
                 entity_id=None, merchant_name=None):
    txn = Transaction(
        user_id=user.id, amount=amount, description=description,
        category=category, transaction_type='expense',
        transaction_date=when, transaction_notes='', source='plaid',
        plaid_transaction_id=f'{description}-{when.isoformat()}-{amount}',
        merchant_name=merchant_name, merchant_entity_id=entity_id
    )
    db.session.add(txn)
    db.session.commit()
    return txn


class TestFromTransactions:
    def test_seed_from_single_transaction(self, client, auth_headers, user):
        """One past rent payment is enough to start tracking going forward."""
        rent = make_expense(user, 'RENT PAYMT #4390', 1500.00, datetime(2026, 4, 1))

        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': [rent.id], 'category': 'RENT_AND_UTILITIES',
                                'name': 'Rent', 'cadence': 'monthly'})
        assert res.status_code == 201
        data = res.get_json()
        assert data['merchant_name'] == 'Rent'
        assert data['confirmed_by_user'] is True
        assert data['cadence'] == 'monthly'
        assert float(data['expected_amount']) == 1500.00
        assert len(data['occurrences']) == 1
        assert data['next_expected_date'] is not None

    def test_seed_infers_cadence_from_multiple(self, client, auth_headers, user):
        """Picking 3 payments lets the server infer the cadence automatically."""
        ids = [make_expense(user, f'RENT PAYMT #{i}', 1500.00,
                            datetime(2026, 4, 1) + timedelta(days=30 * n)).id
               for n, i in enumerate((4390, 4471, 4502))]

        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': ids})  # no cadence provided
        assert res.status_code == 201
        assert res.get_json()['cadence'] == 'monthly'
        assert len(res.get_json()['occurrences']) == 3

    def test_seed_stores_shared_entity_id(self, client, auth_headers, user):
        ids = [make_expense(user, 'RENT PAYMT #4390', 1500.00, datetime(2026, 4, 1),
                            entity_id='ent_rent_123').id,
               make_expense(user, 'RENT PAYMT #4471', 1500.00, datetime(2026, 5, 1),
                            entity_id='ent_rent_123').id]

        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': ids})
        assert res.status_code == 201
        assert res.get_json()['merchant_entity_id'] == 'ent_rent_123'

    def test_seed_leaves_entity_null_when_ids_disagree(self, client, auth_headers, user):
        ids = [make_expense(user, 'RENT PAYMT #4390', 1500.00, datetime(2026, 4, 1),
                            entity_id='ent_a').id,
               make_expense(user, 'RENT PAYMT #4471', 1500.00, datetime(2026, 5, 1),
                            entity_id='ent_b').id]

        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': ids})
        assert res.get_json()['merchant_entity_id'] is None

    def test_rejects_more_than_three(self, client, auth_headers, user):
        ids = [make_expense(user, f'X{n}', 10.00, datetime(2026, 4, 1) + timedelta(days=n)).id
               for n in range(4)]
        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': ids})
        assert res.status_code == 400
        assert 'at most 3' in res.get_json()['error']

    def test_rejects_empty(self, client, auth_headers, user):
        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': []})
        assert res.status_code == 400

    def test_rejects_already_tracked(self, client, auth_headers, user):
        rent = make_expense(user, 'RENT PAYMT #4390', 1500.00, datetime(2026, 4, 1))
        client.post('/api/recurring/from-transactions', headers=auth_headers,
                    json={'transaction_ids': [rent.id]})
        # try to seed a second series from the same transaction
        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': [rent.id]})
        assert res.status_code == 400
        assert 'already tracked' in res.get_json()['error']

    def test_expected_amount_override(self, client, auth_headers, user):
        rent = make_expense(user, 'RENT PAYMT #4390', 1490.00, datetime(2026, 4, 1))
        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': [rent.id], 'expected_amount': 1500.00})
        assert float(res.get_json()['expected_amount']) == 1500.00


class TestFutureMatching:
    def _seed_rent(self, client, auth_headers, user, entity_id=None):
        rent = make_expense(user, 'RENT PAYMT #4390', 1500.00, datetime(2026, 4, 1),
                            entity_id=entity_id)
        res = client.post('/api/recurring/from-transactions', headers=auth_headers,
                          json={'transaction_ids': [rent.id], 'name': 'Rent',
                                'cadence': 'monthly'})
        return RecurringExpense.query.get(res.get_json()['id'])

    def test_matches_by_entity_id(self, client, auth_headers, user):
        """Even with a totally different description, a shared entity id matches."""
        series = self._seed_rent(client, auth_headers, user, entity_id='ent_rent_1')
        # next month, wildly different description text but same entity id + amount
        make_expense(user, 'ACH WEB PMT LANDLORD LLC', 1500.00, datetime(2026, 5, 1),
                     entity_id='ent_rent_1')
        result = detect_recurring(user.id)
        assert result['new_occurrences'] == 1
        assert result['new_candidates'] == 0
        assert len(RecurringExpense.query.get(series.id).occurrences) == 2

    def test_matches_by_exact_normalized_name(self, client, auth_headers, user):
        """Description varies only by the check number -> normalized key matches."""
        series = self._seed_rent(client, auth_headers, user)
        make_expense(user, 'RENT PAYMT #4471', 1500.00, datetime(2026, 5, 1))
        result = detect_recurring(user.id)
        assert result['new_occurrences'] == 1
        assert len(RecurringExpense.query.get(series.id).occurrences) == 2

    def test_matches_by_amount_and_date_window(self, client, auth_headers, user):
        """Different description text, no entity id -> falls back to amount+date."""
        series = self._seed_rent(client, auth_headers, user)
        # ~1 month later (within window), same amount, unrelated-looking text
        make_expense(user, 'ONLINE TRANSFER TO PROPERTY MGMT', 1500.00, datetime(2026, 5, 3))
        result = detect_recurring(user.id)
        assert result['new_occurrences'] == 1
        assert len(RecurringExpense.query.get(series.id).occurrences) == 2

    def test_no_match_outside_date_window(self, client, auth_headers, user):
        """Same amount but way off-schedule and different name -> not matched."""
        self._seed_rent(client, auth_headers, user)
        # 15 days off the ~May 1 projection, different text
        make_expense(user, 'RANDOM BIG PURCHASE STORE', 1500.00, datetime(2026, 5, 16))
        result = detect_recurring(user.id)
        assert result['new_occurrences'] == 0

    def test_no_match_wrong_amount_in_window(self, client, auth_headers, user):
        """On-schedule but amount far off (>2%) and different name -> not matched."""
        self._seed_rent(client, auth_headers, user)
        make_expense(user, 'DIFFERENT MERCHANT ENTIRELY', 1800.00, datetime(2026, 5, 2))
        result = detect_recurring(user.id)
        assert result['new_occurrences'] == 0

    def test_multiple_months_roll_forward(self, client, auth_headers, user):
        """Successive months keep matching as the schedule advances."""
        series = self._seed_rent(client, auth_headers, user)
        make_expense(user, 'RENT PAYMT #4471', 1500.00, datetime(2026, 5, 1))
        make_expense(user, 'RENT PAYMT #4502', 1500.00, datetime(2026, 6, 1))
        make_expense(user, 'RENT PAYMT #4533', 1500.00, datetime(2026, 7, 1))
        result = detect_recurring(user.id)
        assert result['new_occurrences'] == 3
        assert len(RecurringExpense.query.get(series.id).occurrences) == 4


class TestManualAnchor:
    def test_manual_entry_sets_next_expected_date(self, client, auth_headers, user):
        """The free-text fallback anchors a schedule so date-window matching works."""
        res = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES', 'expected_amount': 1500.00,
            'cadence': 'monthly', 'description': 'Rent',
            'next_expected_date': '2026-05-01'
        })
        assert res.status_code == 201
        assert res.get_json()['next_expected_date'] == '2026-05-01'

    def test_manual_entry_matches_future_by_amount_date(self, client, auth_headers, user):
        client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES', 'expected_amount': 1500.00,
            'cadence': 'monthly', 'description': 'Rent',
            'next_expected_date': '2026-05-01'
        })
        make_expense(user, 'SOME LANDLORD ACH', 1500.00, datetime(2026, 5, 2))
        result = detect_recurring(user.id)
        assert result['new_occurrences'] == 1
