"""
Tests for Bug Fixes:
1. Bug 2: Delete/Restore Envelopes (soft delete)
2. Bug 3: Manual Recurring Expense Creation
"""
import pytest
from datetime import datetime
from models.user import db
from models.goal import FinancialGoal
from models.recurring import RecurringExpense
from tests.conftest import make_goal


class TestEnvelopeDeletion:
    """Bug 2: Hard delete with undo (soft delete at DB layer)"""

    def test_delete_envelope_sets_deleted_at(self, client, auth_headers, user, account):
        """Soft-delete a goal: DELETE /envelopes/{goal_id} sets deleted_at timestamp"""
        goal = make_goal(user, 'Hajj', linked_account_id=account.id)

        response = client.delete(f'/api/envelopes/envelopes/{goal.id}', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Goal deleted. You can restore it within 30 days.'
        assert data['goal']['id'] == goal.id

        # Verify deleted_at is set
        db.session.refresh(goal)
        assert goal.deleted_at is not None

    def test_cannot_double_delete(self, client, auth_headers, user, account):
        """Cannot delete an already-deleted goal"""
        goal = make_goal(user, 'Hajj', linked_account_id=account.id)

        # First delete succeeds
        response1 = client.delete(f'/api/envelopes/envelopes/{goal.id}', headers=auth_headers)
        assert response1.status_code == 200

        # Second delete fails
        response2 = client.delete(f'/api/envelopes/envelopes/{goal.id}', headers=auth_headers)
        assert response2.status_code == 409
        assert 'already deleted' in response2.get_json()['error']

    def test_restore_envelope_clears_deleted_at(self, client, auth_headers, user, account):
        """Restore a soft-deleted goal: POST /envelopes/{goal_id}/restore clears deleted_at"""
        goal = make_goal(user, 'Hajj', linked_account_id=account.id)

        # Delete
        client.delete(f'/api/envelopes/envelopes/{goal.id}', headers=auth_headers)
        db.session.refresh(goal)
        assert goal.deleted_at is not None

        # Restore
        response = client.post(f'/api/envelopes/envelopes/{goal.id}/restore', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Goal restored'

        db.session.refresh(goal)
        assert goal.deleted_at is None

    def test_cannot_restore_non_deleted_goal(self, client, auth_headers, user, account):
        """Cannot restore a goal that hasn't been deleted"""
        goal = make_goal(user, 'Hajj', linked_account_id=account.id)

        response = client.post(f'/api/envelopes/envelopes/{goal.id}/restore', headers=auth_headers)

        assert response.status_code == 400
        assert 'not deleted' in response.get_json()['error']

    def test_deleted_goals_hidden_from_reconciliation(self, client, auth_headers, user, account):
        """Deleted goals don't appear in reconciliation view"""
        goal1 = make_goal(user, 'Active', linked_account_id=account.id)
        goal2 = make_goal(user, 'Deleted', linked_account_id=account.id)

        # Delete goal2
        client.delete(f'/api/envelopes/envelopes/{goal2.id}', headers=auth_headers)

        # Fetch reconciliation
        response = client.get('/api/envelopes/reconciliation', headers=auth_headers)
        assert response.status_code == 200

        data = response.get_json()
        account_entry = data[0]
        envelopes = account_entry['envelopes']

        # Only active goal should appear
        goal_names = [e['goal_name'] for e in envelopes]
        assert 'Active' in goal_names
        assert 'Deleted' not in goal_names

    def test_deleted_goals_hidden_from_goals_list(self, client, auth_headers, user):
        """Deleted goals don't appear in GET /api/goals"""
        goal1 = make_goal(user, 'Active')
        goal2 = make_goal(user, 'Deleted')

        # Delete goal2
        response = client.delete(f'/api/goals/{goal2.id}', headers=auth_headers)
        assert response.status_code == 200

        # Fetch goals
        response = client.get('/api/goals', headers=auth_headers)
        assert response.status_code == 200

        goals = response.get_json()
        goal_names = [g['name'] for g in goals]
        assert 'Active' in goal_names
        assert 'Deleted' not in goal_names

    def test_cannot_update_deleted_goal(self, client, auth_headers, user):
        """Cannot update a deleted goal"""
        goal = make_goal(user, 'Hajj')

        # Delete goal
        client.delete(f'/api/goals/{goal.id}', headers=auth_headers)

        # Try to update
        response = client.put(f'/api/goals/{goal.id}',
                             json={'name': 'New Name'},
                             headers=auth_headers)

        assert response.status_code == 404
        assert 'not found' in response.get_json()['error']

    def test_cannot_add_progress_to_deleted_goal(self, client, auth_headers, user):
        """Cannot add progress to a deleted goal"""
        goal = make_goal(user, 'Hajj')

        # Delete goal
        client.delete(f'/api/goals/{goal.id}', headers=auth_headers)

        # Try to add progress
        response = client.post(f'/api/goals/{goal.id}/add-progress',
                              json={'amount': 100},
                              headers=auth_headers)

        assert response.status_code == 404
        assert 'not found' in response.get_json()['error']


class TestManualRecurringExpense:
    """Bug 3: Manual recurring expense creation for cases with < 3 transactions"""

    def test_create_manual_recurring_expense(self, client, auth_headers, user):
        """POST /manual creates a recurring expense without relying on detection"""
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 1500.00,
            'cadence': 'monthly',
            'description': 'Apartment rent'
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data['merchant_name'] == 'Apartment rent'
        assert data['category'] == 'RENT_AND_UTILITIES'
        assert float(data['expected_amount']) == 1500.00
        assert data['cadence'] == 'monthly'
        assert data['confirmed_by_user'] is True
        assert data['status'] == 'active'

    def test_manual_recurring_requires_category(self, client, auth_headers, user):
        """Category is required"""
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'expected_amount': 1500.00,
            'cadence': 'monthly',
            'description': 'Rent'
        })

        assert response.status_code == 400
        assert 'category required' in response.get_json()['error']

    def test_manual_recurring_requires_amount(self, client, auth_headers, user):
        """Amount is required"""
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'cadence': 'monthly',
            'description': 'Rent'
        })

        assert response.status_code == 400
        assert 'expected_amount required' in response.get_json()['error']

    def test_manual_recurring_requires_cadence(self, client, auth_headers, user):
        """Cadence is required"""
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 1500.00,
            'description': 'Rent'
        })

        assert response.status_code == 400
        assert 'cadence required' in response.get_json()['error']

    def test_manual_recurring_validates_cadence(self, client, auth_headers, user):
        """Invalid cadence is rejected"""
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 1500.00,
            'cadence': 'invalid',
            'description': 'Rent'
        })

        assert response.status_code == 400
        assert 'cadence must be one of' in response.get_json()['error']

    def test_manual_recurring_validates_positive_amount(self, client, auth_headers, user):
        """Amount must be positive"""
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 0,
            'cadence': 'monthly',
            'description': 'Rent'
        })

        assert response.status_code == 400
        assert 'must be positive' in response.get_json()['error']

    def test_manual_recurring_appears_in_confirmed_list(self, client, auth_headers, user):
        """Manually created recurring expenses appear in confirmed list immediately"""
        # Create manual entry
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 1500.00,
            'cadence': 'monthly',
            'description': 'Apartment rent'
        })
        assert response.status_code == 201

        # Fetch confirmed list
        response = client.get('/api/recurring?status=confirmed', headers=auth_headers)
        assert response.status_code == 200

        recurring = response.get_json()
        assert len(recurring) == 1
        assert recurring[0]['merchant_name'] == 'Apartment rent'
        assert recurring[0]['confirmed_by_user'] is True

    def test_manual_recurring_not_in_review_queue(self, client, auth_headers, user):
        """Manually created entries skip the review queue"""
        # Create manual entry
        client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 1500.00,
            'cadence': 'monthly',
            'description': 'Rent'
        })

        # Fetch review queue
        response = client.get('/api/recurring?status=review', headers=auth_headers)
        assert response.status_code == 200

        review_queue = response.get_json()
        assert len(review_queue) == 0

    def test_manual_recurring_included_in_summary(self, client, auth_headers, user):
        """Manual recurring expenses are included in budget summary"""
        # Create manual entry
        client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 1500.00,
            'cadence': 'monthly',
            'description': 'Rent'
        })

        # Fetch summary
        response = client.get('/api/recurring/summary', headers=auth_headers)
        assert response.status_code == 200

        summary = response.get_json()
        assert summary['total_monthly'] == 1500.00
        assert len(summary['categories']) == 1
        assert summary['categories'][0]['category'] == 'RENT_AND_UTILITIES'
        assert summary['categories'][0]['monthly_total'] == 1500.00

    def test_manual_recurring_with_all_cadences(self, client, auth_headers, user):
        """Manual recurring works with all cadence types"""
        cadences = ['weekly', 'biweekly', 'monthly', 'annual']
        expected_monthly = {
            'weekly': 433.33,      # ~4.33 weeks per month
            'biweekly': 216.67,    # ~2.17 periods per month
            'monthly': 100.00,
            'annual': 8.33         # 100 / 12
        }

        for cadence in cadences:
            response = client.post('/api/recurring/manual', headers=auth_headers, json={
                'category': 'GENERAL_SERVICES',
                'expected_amount': 100.00,
                'cadence': cadence,
                'description': f'Test {cadence}'
            })

            assert response.status_code == 201
            data = response.get_json()
            assert data['cadence'] == cadence
            # Check monthly_equivalent is calculated
            assert data['monthly_equivalent'] > 0

    def test_manual_recurring_without_description_defaults_to_manual_entry(self, client, auth_headers, user):
        """If no description provided, merchant_name defaults to 'Manual Entry'"""
        response = client.post('/api/recurring/manual', headers=auth_headers, json={
            'category': 'RENT_AND_UTILITIES',
            'expected_amount': 1500.00,
            'cadence': 'monthly'
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data['merchant_name'] == 'Manual Entry'
