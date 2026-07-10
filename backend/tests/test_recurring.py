from datetime import datetime, timedelta
from decimal import Decimal

from models.user import db
from models.transaction import Transaction
from models.recurring import RecurringExpense, RecurringExpenseOccurrence
from utils.recurring import detect_recurring, normalize_merchant, infer_cadence


def make_expense(user, description, amount, when, category='ENTERTAINMENT'):
    txn = Transaction(
        user_id=user.id, amount=amount, description=description,
        category=category, transaction_type='expense',
        transaction_date=when, transaction_notes='', source='plaid',
        plaid_transaction_id=f'{description}-{when.isoformat()}-{amount}'
    )
    db.session.add(txn)
    db.session.commit()
    return txn


def monthly_series(user, description='Netflix.com', amount=15.49, months=3,
                   start=datetime(2026, 3, 5), category='ENTERTAINMENT', jitter_days=0):
    txns = []
    for i in range(months):
        when = start + timedelta(days=30 * i + (jitter_days if i % 2 else 0))
        txns.append(make_expense(user, description, amount, when, category))
    return txns


class TestHelpers:
    def test_normalize_merchant(self, app):
        assert normalize_merchant('NETFLIX.COM *123') == normalize_merchant('Netflix Com')
        assert normalize_merchant('SPOTIFY P0123456') == 'spotify p'

    def test_infer_cadence(self, app):
        from datetime import date
        monthly = [date(2026, 1, 5), date(2026, 2, 4), date(2026, 3, 6)]
        assert infer_cadence(monthly) == 'monthly'
        weekly = [date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 15)]
        assert infer_cadence(weekly) == 'weekly'
        biweekly = [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29)]
        assert infer_cadence(biweekly) == 'biweekly'
        annual = [date(2024, 3, 1), date(2025, 3, 2), date(2026, 3, 1)]
        assert infer_cadence(annual) == 'annual'
        irregular = [date(2026, 1, 1), date(2026, 1, 20), date(2026, 3, 1)]
        assert infer_cadence(irregular) is None


class TestDetection:
    def test_monthly_subscription_detected(self, app, user):
        monthly_series(user, months=4)
        result = detect_recurring(user.id)
        assert result['new_candidates'] == 1

        series = RecurringExpense.query.one()
        assert series.cadence == 'monthly'
        assert series.confirmed_by_user is False
        assert series.category == 'ENTERTAINMENT'
        assert float(series.expected_amount) == 15.49
        assert len(series.occurrences) == 4
        assert series.next_expected_date is not None

    def test_two_occurrences_not_enough(self, app, user):
        monthly_series(user, months=2)
        assert detect_recurring(user.id)['new_candidates'] == 0

    def test_irregular_intervals_not_flagged(self, app, user):
        for day in (datetime(2026, 1, 3), datetime(2026, 1, 20), datetime(2026, 3, 15)):
            make_expense(user, 'Corner Cafe', 12.50, day)
        assert detect_recurring(user.id)['new_candidates'] == 0

    def test_variable_amounts_not_flagged(self, app, user):
        # Same store, monthly-ish, but amounts differ way beyond 15% (grocery runs)
        for i, amount in enumerate((45.00, 92.00, 140.00)):
            make_expense(user, 'Whole Foods', amount, datetime(2026, 1, 5) + timedelta(days=30 * i))
        assert detect_recurring(user.id)['new_candidates'] == 0

    def test_one_off_at_same_merchant_does_not_break_cluster(self, app, user):
        monthly_series(user, months=3)
        make_expense(user, 'Netflix.com', 200.00, datetime(2026, 3, 20))  # gift card
        result = detect_recurring(user.id)
        assert result['new_candidates'] == 1
        assert len(RecurringExpense.query.one().occurrences) == 3

    def test_detection_idempotent_and_attaches_new_charges(self, app, user):
        monthly_series(user, months=3)
        detect_recurring(user.id)
        assert detect_recurring(user.id) == {'new_candidates': 0, 'new_occurrences': 0}

        # next month's charge arrives -> attached, not re-flagged
        make_expense(user, 'Netflix.com', 15.49, datetime(2026, 6, 3))
        result = detect_recurring(user.id)
        assert result == {'new_candidates': 0, 'new_occurrences': 1}
        series = RecurringExpense.query.one()
        assert len(series.occurrences) == 4

    def test_dismissed_series_absorbs_matches_silently(self, app, user):
        monthly_series(user, months=3)
        detect_recurring(user.id)
        series = RecurringExpense.query.one()
        series.status = 'dismissed'
        db.session.commit()

        make_expense(user, 'Netflix.com', 15.49, datetime(2026, 6, 3))
        result = detect_recurring(user.id)
        assert result == {'new_candidates': 0, 'new_occurrences': 0}
        assert RecurringExpense.query.count() == 1

    def test_price_creep_flagged(self, app, user):
        monthly_series(user, months=3, amount=15.49)
        detect_recurring(user.id)
        # price hike within cluster tolerance but above creep threshold
        make_expense(user, 'Netflix.com', 17.49, datetime(2026, 6, 3))
        detect_recurring(user.id)

        series = RecurringExpense.query.one()
        creep = series.price_creep
        assert creep is not None
        assert creep['latest_amount'] == 17.49
        assert creep['previous_average'] == 15.49
        assert creep['increase_pct'] > 10

    def test_no_price_creep_when_stable(self, app, user):
        monthly_series(user, months=4)
        detect_recurring(user.id)
        assert RecurringExpense.query.one().price_creep is None


class TestRecurringEndpoints:
    def seed_candidate(self, client, headers, user):
        monthly_series(user, months=3)
        client.post('/api/recurring/detect', headers=headers)
        return RecurringExpense.query.one()

    def test_detect_and_review_queue(self, client, auth_headers, user):
        self.seed_candidate(client, auth_headers, user)
        res = client.get('/api/recurring?status=review', headers=auth_headers)
        assert res.status_code == 200
        items = res.get_json()
        assert len(items) == 1
        assert items[0]['confirmed_by_user'] is False
        assert len(items[0]['occurrences']) == 3

    def test_confirm_moves_out_of_review(self, client, auth_headers, user):
        series = self.seed_candidate(client, auth_headers, user)
        res = client.post(f'/api/recurring/{series.id}/confirm', headers=auth_headers,
                          json={'category': 'SUBSCRIPTIONS'})
        assert res.status_code == 200
        assert res.get_json()['confirmed_by_user'] is True
        assert res.get_json()['category'] == 'SUBSCRIPTIONS'
        assert client.get('/api/recurring?status=review', headers=auth_headers).get_json() == []
        assert len(client.get('/api/recurring?status=confirmed', headers=auth_headers).get_json()) == 1

    def test_dismiss(self, client, auth_headers, user):
        series = self.seed_candidate(client, auth_headers, user)
        res = client.post(f'/api/recurring/{series.id}/dismiss', headers=auth_headers)
        assert res.status_code == 200
        assert client.get('/api/recurring?status=review', headers=auth_headers).get_json() == []

    def test_update_cadence_and_cancel(self, client, auth_headers, user):
        series = self.seed_candidate(client, auth_headers, user)
        res = client.put(f'/api/recurring/{series.id}', headers=auth_headers,
                         json={'cadence': 'annual'})
        assert res.get_json()['cadence'] == 'annual'

        res = client.put(f'/api/recurring/{series.id}', headers=auth_headers,
                         json={'status': 'cancelled_by_user'})
        assert res.get_json()['status'] == 'cancelled_by_user'

        res = client.put(f'/api/recurring/{series.id}', headers=auth_headers,
                         json={'cadence': 'fortnightly'})
        assert res.status_code == 400

    def test_summary_monthly_equivalents(self, client, auth_headers, user):
        # monthly 15.49 (ENTERTAINMENT) + weekly 10.00 (FOOD_AND_DRINK)
        monthly_series(user, months=3)
        for i in range(3):
            make_expense(user, 'HelloFresh', 10.00,
                         datetime(2026, 5, 1) + timedelta(days=7 * i), category='FOOD_AND_DRINK')
        client.post('/api/recurring/detect', headers=auth_headers)
        for series in RecurringExpense.query.all():
            client.post(f'/api/recurring/{series.id}/confirm', headers=auth_headers)

        res = client.get('/api/recurring/summary', headers=auth_headers)
        data = res.get_json()
        by_cat = {c['category']: c for c in data['categories']}
        assert by_cat['ENTERTAINMENT']['monthly_total'] == 15.49
        assert by_cat['FOOD_AND_DRINK']['monthly_total'] == 43.33  # 10 * 52/12
        assert data['total_monthly'] == 58.82

    def test_summary_excludes_unconfirmed_and_dismissed(self, client, auth_headers, user):
        series = self.seed_candidate(client, auth_headers, user)
        assert client.get('/api/recurring/summary', headers=auth_headers).get_json()['total_monthly'] == 0

        client.post(f'/api/recurring/{series.id}/confirm', headers=auth_headers)
        assert client.get('/api/recurring/summary', headers=auth_headers).get_json()['total_monthly'] == 15.49
