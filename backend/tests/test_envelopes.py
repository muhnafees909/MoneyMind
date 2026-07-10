from models.user import db
from models.envelope import EnvelopeAllocation
from tests.conftest import make_goal


def allocate(client, headers, goal_id, amount, source_type='manual', note=None):
    return client.post('/api/envelopes/allocations', headers=headers,
                       json={'goal_id': goal_id, 'amount': amount,
                             'source_type': source_type, 'note': note})


class TestAllocations:
    def test_manual_allocation_updates_ledger_and_goal(self, client, auth_headers, linked_goal):
        res = allocate(client, auth_headers, linked_goal.id, 250.50)
        assert res.status_code == 201
        body = res.get_json()
        assert body['envelope_balance'] == 250.50
        assert body['goal']['current_amount'] == 250.50
        assert body['allocation']['source_type'] == 'manual'

    def test_allocation_requires_linked_account(self, client, auth_headers, user):
        goal = make_goal(user, name='Unlinked')
        res = allocate(client, auth_headers, goal.id, 100)
        assert res.status_code == 400
        assert 'not linked' in res.get_json()['error']

    def test_withdrawal_is_negative_and_capped(self, client, auth_headers, linked_goal):
        allocate(client, auth_headers, linked_goal.id, 300)

        res = allocate(client, auth_headers, linked_goal.id, 500, source_type='withdrawal')
        assert res.status_code == 400  # can't withdraw more than the envelope holds

        res = allocate(client, auth_headers, linked_goal.id, 100, source_type='withdrawal')
        assert res.status_code == 201
        assert res.get_json()['envelope_balance'] == 200.0
        assert res.get_json()['allocation']['amount'] == -100.0

    def test_invalid_amounts_rejected(self, client, auth_headers, linked_goal):
        for bad in (0, -50, 'abc', None):
            res = allocate(client, auth_headers, linked_goal.id, bad)
            assert res.status_code == 400

    def test_goal_completes_when_target_reached(self, client, auth_headers, linked_goal):
        res = allocate(client, auth_headers, linked_goal.id, 2000)  # target is 2000
        assert res.get_json()['goal']['is_completed'] is True

    def test_other_users_goal_not_found(self, client, auth_headers, app, account):
        from models.user import User
        other = User(email='other@example.com', first_name='Other')
        other.set_password('pw')
        db.session.add(other)
        db.session.commit()
        goal = make_goal(other, linked_account_id=account.id)
        res = allocate(client, auth_headers, goal.id, 100)
        assert res.status_code == 404

    def test_allocation_history(self, client, auth_headers, linked_goal):
        allocate(client, auth_headers, linked_goal.id, 100)
        allocate(client, auth_headers, linked_goal.id, 50, source_type='withdrawal')
        res = client.get(f'/api/envelopes/allocations?goal_id={linked_goal.id}',
                         headers=auth_headers)
        assert res.status_code == 200
        amounts = [a['amount'] for a in res.get_json()]
        assert sorted(amounts) == [-50.0, 100.0]


class TestGoalEnvelopeSync:
    def test_add_progress_writes_ledger_row_for_linked_goal(self, client, auth_headers, linked_goal):
        res = client.post(f'/api/goals/{linked_goal.id}/add-progress',
                          headers=auth_headers, json={'amount': 75.25})
        assert res.status_code == 200
        assert res.get_json()['current_amount'] == 75.25
        rows = EnvelopeAllocation.query.filter_by(goal_id=linked_goal.id).all()
        assert len(rows) == 1
        assert float(rows[0].amount) == 75.25

    def test_add_progress_decimal_amount_on_unlinked_goal(self, client, auth_headers, user):
        # Regression: Decimal + float used to raise TypeError for non-integer amounts
        goal = make_goal(user, name='Unlinked')
        res = client.post(f'/api/goals/{goal.id}/add-progress',
                          headers=auth_headers, json={'amount': 50.25})
        assert res.status_code == 200
        assert res.get_json()['current_amount'] == 50.25

    def test_linking_goal_seeds_ledger_with_existing_amount(self, client, auth_headers, user, account):
        goal = make_goal(user, name='Marriage', current=500)
        res = client.put(f'/api/goals/{goal.id}', headers=auth_headers,
                         json={'name': 'Marriage', 'target_amount': 3500,
                               'linked_account_id': account.id})
        assert res.status_code == 200
        rows = EnvelopeAllocation.query.filter_by(goal_id=goal.id).all()
        assert len(rows) == 1
        assert float(rows[0].amount) == 500.0
        assert rows[0].source_type == 'correction'
        assert res.get_json()['current_amount'] == 500.0

    def test_editing_current_amount_on_linked_goal_writes_correction(self, client, auth_headers, linked_goal):
        client.post('/api/envelopes/allocations', headers=auth_headers,
                    json={'goal_id': linked_goal.id, 'amount': 300})
        res = client.put(f'/api/goals/{linked_goal.id}', headers=auth_headers,
                         json={'current_amount': 250})
        assert res.status_code == 200
        assert res.get_json()['current_amount'] == 250.0
        rows = EnvelopeAllocation.query.filter_by(goal_id=linked_goal.id,
                                                  source_type='correction').all()
        assert len(rows) == 1
        assert float(rows[0].amount) == -50.0


class TestReconciliation:
    def test_breakdown_per_account(self, client, auth_headers, user, account):
        hajj = make_goal(user, name='Hajj', linked_account_id=account.id)
        marriage = make_goal(user, name='Marriage', target=3500, linked_account_id=account.id)
        allocate(client, auth_headers, hajj.id, 200)
        allocate(client, auth_headers, marriage.id, 300)

        res = client.get('/api/envelopes/reconciliation', headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert len(data) == 1
        acct = data[0]
        assert acct['actual_balance'] == 1000.0
        assert acct['allocated_total'] == 500.0
        assert acct['unallocated_cash'] == 500.0
        assert {e['goal_name']: e['envelope_balance'] for e in acct['envelopes']} == \
               {'Hajj': 200.0, 'Marriage': 300.0}
        assert all(e['counter_drift'] == 0 for e in acct['envelopes'])

    def test_account_with_no_envelopes(self, client, auth_headers, account):
        res = client.get('/api/envelopes/reconciliation', headers=auth_headers)
        data = res.get_json()
        assert data[0]['allocated_total'] == 0.0
        assert data[0]['unallocated_cash'] == 1000.0
        assert data[0]['envelopes'] == []


class TestAllocationRules:
    def test_rule_crud(self, client, auth_headers, linked_goal):
        res = client.post('/api/envelopes/rules', headers=auth_headers,
                          json={'goal_id': linked_goal.id, 'priority_order': 1,
                                'allocation_type': 'fixed_amount', 'fixed_amount': 400})
        assert res.status_code == 201
        rule_id = res.get_json()['id']

        # duplicate rule for same goal rejected
        res = client.post('/api/envelopes/rules', headers=auth_headers,
                          json={'goal_id': linked_goal.id, 'priority_order': 2,
                                'allocation_type': 'remainder'})
        assert res.status_code == 400

        res = client.put(f'/api/envelopes/rules/{rule_id}', headers=auth_headers,
                         json={'priority_order': 3})
        assert res.get_json()['priority_order'] == 3

        res = client.delete(f'/api/envelopes/rules/{rule_id}', headers=auth_headers)
        assert res.status_code == 200
        assert client.get('/api/envelopes/rules', headers=auth_headers).get_json() == []

    def test_rule_validation(self, client, auth_headers, linked_goal):
        res = client.post('/api/envelopes/rules', headers=auth_headers,
                          json={'goal_id': linked_goal.id, 'priority_order': 1,
                                'allocation_type': 'percentage', 'percentage': 150})
        assert res.status_code == 400

        res = client.post('/api/envelopes/rules', headers=auth_headers,
                          json={'goal_id': linked_goal.id, 'priority_order': 1,
                                'allocation_type': 'fixed_amount'})
        assert res.status_code == 400

        res = client.post('/api/envelopes/rules', headers=auth_headers,
                          json={'goal_id': linked_goal.id, 'priority_order': 1,
                                'allocation_type': 'bogus'})
        assert res.status_code == 400
