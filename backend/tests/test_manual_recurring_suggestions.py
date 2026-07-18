"""
Manually entered transactions must feed recurring detection exactly like
Plaid-synced ones: entering the Nth rent payment by hand should surface a
recurring-expense suggestion without the user ever visiting the detect
endpoint or syncing a bank.
"""

from models.recurring import RecurringExpense, RecurringExpenseOccurrence
from models.transaction import Transaction


def add_manual(client, headers, amount, description, dt, category='RENT_AND_UTILITIES'):
    return client.post('/api/transactions/', headers=headers, json={
        'amount': amount,
        'description': description,
        'category': category,
        'transaction_date': dt
    })


class TestManualEntryDetection:
    def test_monthly_manual_rent_creates_suggestion(self, client, auth_headers, user):
        """Messy-but-similar descriptions + small amount drift + monthly gaps
        → one unconfirmed candidate in the review queue."""
        entries = [
            (1550.00, 'Rent - Maple St', '2026-04-01'),
            (1550.00, 'rent maple st', '2026-05-01'),
            (1560.00, 'RENT Maple St.', '2026-06-01'),
            (1550.00, 'Rent — Maple St', '2026-07-01'),
        ]
        for amount, desc, dt in entries:
            assert add_manual(client, auth_headers, amount, desc, dt).status_code == 201

        candidates = RecurringExpense.query.filter_by(
            user_id=user.id, confirmed_by_user=False, status='active').all()
        assert len(candidates) == 1
        series = candidates[0]
        assert series.cadence == 'monthly'
        assert len(series.occurrences) == 4
        # Expected amount averages the cluster
        assert 1549 < float(series.expected_amount) < 1556

        # And it shows up where the dashboard banner looks
        res = client.get('/api/recurring?status=review', headers=auth_headers)
        assert res.status_code == 200
        review = res.get_json()
        assert len(review) == 1
        assert review[0]['occurrence_count'] == 4

    def test_two_occurrences_not_yet_suggested(self, client, auth_headers, user):
        add_manual(client, auth_headers, 60, 'Gym membership', '2026-05-15')
        add_manual(client, auth_headers, 60, 'Gym membership', '2026-06-15')
        assert RecurringExpense.query.filter_by(user_id=user.id).count() == 0

        # The third strike completes the pattern
        add_manual(client, auth_headers, 60, 'Gym membership', '2026-07-15')
        assert RecurringExpense.query.filter_by(
            user_id=user.id, confirmed_by_user=False).count() == 1

    def test_irregular_manual_charges_not_flagged(self, client, auth_headers, user):
        """Same merchant, erratic dates — no cadence, no suggestion."""
        for amount, dt in ((45.0, '2026-06-02'), (45.0, '2026-06-11'),
                           (45.0, '2026-07-01'), (45.0, '2026-07-05')):
            add_manual(client, auth_headers, amount, 'Corner cafe', dt,
                       category='FOOD_AND_DRINK')
        assert RecurringExpense.query.filter_by(user_id=user.id).count() == 0

    def test_confirm_flow_uses_same_model(self, client, auth_headers, user):
        """The suggestion feeds the standard recurring_expenses flow: confirm
        makes it a normal confirmed series that the summary endpoint counts."""
        for i, dt in enumerate(('2026-05-01', '2026-06-01', '2026-07-01')):
            add_manual(client, auth_headers, 1550, 'Rent', dt)

        series = RecurringExpense.query.filter_by(user_id=user.id).one()
        res = client.post(f'/api/recurring/{series.id}/confirm', headers=auth_headers)
        assert res.status_code == 200
        assert res.get_json()['confirmed_by_user'] is True

        summary = client.get('/api/recurring/summary', headers=auth_headers).get_json()
        assert summary['total_monthly'] == 1550.0

    def test_deleting_linked_manual_transaction_works(self, client, auth_headers, user):
        """Deleting a transaction that became a recurring occurrence must not
        hit the FK constraint."""
        ids = []
        for dt in ('2026-05-01', '2026-06-01', '2026-07-01'):
            res = add_manual(client, auth_headers, 1550, 'Rent', dt)
            ids.append(res.get_json()['id'])

        assert RecurringExpenseOccurrence.query.count() == 3
        res = client.delete(f'/api/transactions/{ids[-1]}', headers=auth_headers)
        assert res.status_code == 200
        assert Transaction.query.filter_by(id=ids[-1]).first() is None
        assert RecurringExpenseOccurrence.query.count() == 2
