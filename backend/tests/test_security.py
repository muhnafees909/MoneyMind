"""
Security tests: route protection, cross-user isolation (IDOR),
session expiry, and the cookie + CSRF session flow.
"""
from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token

from models.user import db, User
from models.budget import Budget
from models.transaction import Transaction


@pytest.fixture
def other_user(app):
    u = User(email='intruder@example.com', first_name='Intruder')
    u.set_password('password456')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def other_auth_headers(other_user):
    token = create_access_token(identity=str(other_user.id))
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def owned_budget(user):
    budget = Budget(user_id=user.id, category='FOOD_AND_DRINK', amount=500)
    db.session.add(budget)
    db.session.commit()
    return budget


@pytest.fixture
def owned_transaction(user):
    from datetime import datetime
    txn = Transaction(
        user_id=user.id,
        amount=42.50,
        description='Coffee',
        category='FOOD_AND_DRINK',
        transaction_type='expense',
        transaction_date=datetime(2026, 7, 1),
        transaction_notes=''
    )
    db.session.add(txn)
    db.session.commit()
    return txn


class TestRouteProtection:
    """Every data endpoint must reject unauthenticated requests with 401."""

    PROTECTED_GETS = [
        '/api/transactions/',
        '/api/budgets',
        '/api/goals',
        '/api/analytics/spending-summary',
        '/api/envelopes/reconciliation',
        '/api/recurring',
        '/api/profile',
        '/api/auth/me',
    ]

    @pytest.mark.parametrize('path', PROTECTED_GETS)
    def test_get_requires_auth(self, client, path):
        response = client.get(path)
        assert response.status_code == 401
        assert response.get_json()['code'] == 'token_missing'

    def test_mutation_requires_auth(self, client):
        assert client.post('/api/transactions/', json={}).status_code == 401
        assert client.put('/api/profile', json={}).status_code == 401
        assert client.delete('/api/budgets/1').status_code == 401

    def test_garbage_token_rejected(self, client):
        response = client.get(
            '/api/transactions/',
            headers={'Authorization': 'Bearer not-a-real-token'}
        )
        assert response.status_code == 401
        assert response.get_json()['code'] == 'token_invalid'


class TestCrossUserIsolation:
    """Changing an ID in a request must never expose another user's data."""

    def test_other_users_budget_hidden_from_list(
        self, client, owned_budget, other_auth_headers
    ):
        response = client.get('/api/budgets', headers=other_auth_headers)
        assert response.status_code == 200
        assert response.get_json() == []

    def test_cannot_update_other_users_budget(
        self, client, owned_budget, other_auth_headers
    ):
        response = client.put(
            f'/api/budgets/{owned_budget.id}',
            json={'amount': 1},
            headers=other_auth_headers
        )
        # Not found (not 200): resource existence is not confirmed to outsiders
        assert response.status_code == 404
        assert float(Budget.query.get(owned_budget.id).amount) == 500.0

    def test_cannot_delete_other_users_budget(
        self, client, owned_budget, other_auth_headers
    ):
        response = client.delete(
            f'/api/budgets/{owned_budget.id}', headers=other_auth_headers
        )
        assert response.status_code == 404
        assert Budget.query.get(owned_budget.id) is not None

    def test_cannot_touch_other_users_transaction(
        self, client, owned_transaction, other_auth_headers
    ):
        update = client.put(
            f'/api/transactions/{owned_transaction.id}',
            json={'description': 'hacked'},
            headers=other_auth_headers
        )
        delete = client.delete(
            f'/api/transactions/{owned_transaction.id}', headers=other_auth_headers
        )
        assert update.status_code == 404
        assert delete.status_code == 404
        fresh = Transaction.query.get(owned_transaction.id)
        assert fresh is not None
        assert fresh.description == 'Coffee'

    def test_owner_still_has_access(self, client, owned_budget, auth_headers):
        response = client.get('/api/budgets', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.get_json()) == 1


class TestSessionExpiry:
    def test_expired_token_returns_401_with_code(self, client, user, app):
        expired = create_access_token(
            identity=str(user.id), expires_delta=timedelta(seconds=-10)
        )
        response = client.get(
            '/api/transactions/', headers={'Authorization': f'Bearer {expired}'}
        )
        assert response.status_code == 401
        assert response.get_json()['code'] == 'token_expired'


class TestCookieSessionFlow:
    """Browser path: httpOnly cookies + CSRF double-submit + refresh rotation."""

    def _register(self, client):
        return client.post('/api/auth/register', json={
            'email': 'cookie@example.com',
            'password': 'password789',
            'first_name': 'Cookie'
        })

    def test_register_sets_httponly_cookies_and_no_body_token(self, client, app):
        response = self._register(client)
        assert response.status_code == 201
        assert 'access_token' not in response.get_json()

        set_cookies = response.headers.getlist('Set-Cookie')
        access = next(c for c in set_cookies if c.startswith('access_token_cookie='))
        assert 'HttpOnly' in access
        # CSRF cookie must be readable by JS (double-submit pattern)
        csrf = next(c for c in set_cookies if c.startswith('csrf_access_token='))
        assert 'HttpOnly' not in csrf

    def test_cookie_auth_works_and_csrf_is_enforced(self, client, app):
        self._register(client)

        # GET with cookies only — no Authorization header
        assert client.get('/api/transactions/').status_code == 200

        # Mutation WITHOUT the CSRF header must be rejected
        no_csrf = client.put('/api/profile', json={})
        assert no_csrf.status_code == 401

        # Mutation WITH the CSRF header succeeds
        csrf = client.get_cookie('csrf_access_token').value
        with_csrf = client.put(
            '/api/profile', json={}, headers={'X-CSRF-TOKEN': csrf}
        )
        assert with_csrf.status_code == 200

    def test_refresh_rotates_session_and_logout_ends_it(self, client, app):
        self._register(client)
        old_access = client.get_cookie('access_token_cookie').value

        refresh_csrf = client.get_cookie('csrf_refresh_token').value
        refreshed = client.post(
            '/api/auth/refresh', headers={'X-CSRF-TOKEN': refresh_csrf}
        )
        assert refreshed.status_code == 200
        assert client.get_cookie('access_token_cookie').value != old_access

        # Logout clears the cookies; the session is over
        assert client.post('/api/auth/logout').status_code == 200
        assert client.get('/api/transactions/').status_code == 401
