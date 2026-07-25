"""
Transaction amount range validation. A very large amount must be rejected
with a clean 400 (specific message) rather than overflowing the
NUMERIC(10,2) column and surfacing as an unhandled 500.
"""

from datetime import date

from models.transaction import Transaction


def post(client, headers, amount):
    return client.post('/api/transactions/', headers=headers, json={
        'amount': amount, 'description': 'amt test', 'category': 'FOOD_AND_DRINK',
        'transaction_date': date.today().isoformat()
    })


class TestCreateAmountValidation:
    def test_over_column_capacity_is_400_not_500(self, client, auth_headers, user):
        # 12 digits — would overflow NUMERIC(10,2) and 500 before the fix
        res = post(client, auth_headers, 999999999999)
        assert res.status_code == 400
        assert 'too large' in res.get_json()['error'].lower()

    def test_just_over_ceiling_rejected(self, client, auth_headers, user):
        res = post(client, auth_headers, 10000000.01)
        assert res.status_code == 400

    def test_at_ceiling_accepted(self, client, auth_headers, user):
        res = post(client, auth_headers, 10000000)
        assert res.status_code == 201

    def test_normal_amount_accepted(self, client, auth_headers, user):
        res = post(client, auth_headers, 4820.55)
        assert res.status_code == 201
        assert res.get_json()['amount'] == 4820.55

    def test_zero_and_negative_rejected(self, client, auth_headers, user):
        for bad in (0, -5):
            res = post(client, auth_headers, bad)
            assert res.status_code == 400
            assert 'greater than zero' in res.get_json()['error'].lower()

    def test_non_numeric_rejected(self, client, auth_headers, user):
        res = post(client, auth_headers, 'abc')
        assert res.status_code == 400


class TestUpdateAmountValidation:
    def test_update_over_ceiling_rejected(self, client, auth_headers, user):
        created = post(client, auth_headers, 50).get_json()
        res = client.put(f"/api/transactions/{created['id']}", headers=auth_headers,
                         json={'amount': 100000000})
        assert res.status_code == 400
        assert 'too large' in res.get_json()['error'].lower()
        # original amount unchanged
        assert float(Transaction.query.get(created['id']).amount) == 50.0

    def test_update_valid_amount_ok(self, client, auth_headers, user):
        created = post(client, auth_headers, 50).get_json()
        res = client.put(f"/api/transactions/{created['id']}", headers=auth_headers,
                         json={'amount': 275.40})
        assert res.status_code == 200
        assert res.get_json()['amount'] == 275.40
