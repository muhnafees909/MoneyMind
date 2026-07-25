"""
Auth hardening: brute-force lockout, email validation + verification + bank
gating, and TOTP MFA (enroll, two-step login, disable re-auth, backup codes).
"""

import pyotp
import pytest

from models.user import db, User, MfaBackupCode
from models.login_security import LoginAttempt, LoginLockout


def make_user(email='harden@example.com', password='password123', verified=True):
    u = User(email=email, first_name='H', email_verified=verified)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


# ============================================================
# Area 2 — brute-force
# ============================================================

class TestBruteForce:
    def test_non_revealing_error_on_bad_password(self, client):
        make_user(email='real@example.com', password='rightpass')
        r = client.post('/api/auth/login', json={'email': 'real@example.com', 'password': 'wrong'})
        assert r.status_code == 401
        assert r.get_json()['message'] == 'Incorrect email or password'
        # same message for a non-existent account (no enumeration)
        r2 = client.post('/api/auth/login', json={'email': 'nobody@example.com', 'password': 'x'})
        assert r2.get_json()['message'] == 'Incorrect email or password'

    def test_lockout_after_five_failures(self, client):
        make_user(email='lock@example.com', password='rightpass')
        for _ in range(5):
            r = client.post('/api/auth/login', json={'email': 'lock@example.com', 'password': 'bad'})
            assert r.status_code == 401
        # 6th attempt is locked out with a distinct message + Retry-After
        r = client.post('/api/auth/login', json={'email': 'lock@example.com', 'password': 'bad'})
        assert r.status_code == 429
        body = r.get_json()
        assert body['code'] == 'account_locked'
        assert 'locked' in body['message'].lower()
        assert body['retry_after_seconds'] > 0
        assert r.headers.get('Retry-After')

    def test_lockout_blocks_even_correct_password(self, client):
        make_user(email='lock2@example.com', password='rightpass')
        for _ in range(5):
            client.post('/api/auth/login', json={'email': 'lock2@example.com', 'password': 'bad'})
        # correct password now, but locked → still 429
        r = client.post('/api/auth/login', json={'email': 'lock2@example.com', 'password': 'rightpass'})
        assert r.status_code == 429

    def test_failures_are_logged(self, client):
        make_user(email='logged@example.com', password='rightpass')
        client.post('/api/auth/login', json={'email': 'logged@example.com', 'password': 'bad'})
        assert LoginAttempt.query.filter_by(email='logged@example.com', successful=False).count() == 1

    def test_success_clears_streak(self, client):
        make_user(email='clear@example.com', password='rightpass')
        for _ in range(3):
            client.post('/api/auth/login', json={'email': 'clear@example.com', 'password': 'bad'})
        r = client.post('/api/auth/login', json={'email': 'clear@example.com', 'password': 'rightpass'})
        assert r.status_code == 200
        lock = LoginLockout.query.filter_by(email='clear@example.com').first()
        assert lock.fail_count == 0 and lock.locked_until is None


# ============================================================
# Area 4 — email validation, verification, gating
# ============================================================

class TestEmailValidation:
    def test_rejects_malformed_email(self, client):
        r = client.post('/api/auth/register', json={'email': 'not-an-email', 'password': 'password123'})
        assert r.status_code == 400
        assert 'valid email' in r.get_json()['message'].lower()

    def test_rejects_disposable_domain(self, client):
        r = client.post('/api/auth/register',
                        json={'email': 'throwaway@mailinator.com', 'password': 'password123'})
        assert r.status_code == 400
        assert 'disposable' in r.get_json()['message'].lower() or 'permanent' in r.get_json()['message'].lower()

    def test_valid_signup_creates_unverified_user(self, client):
        r = client.post('/api/auth/register',
                        json={'email': 'New.User@Example.com', 'password': 'password123', 'first_name': 'N'})
        assert r.status_code == 201
        body = r.get_json()
        assert body['user']['email_verified'] is False
        # email normalized to lowercase
        u = User.query.filter_by(email='new.user@example.com').one()
        assert u.verification_token_hash is not None  # a token was issued


class TestEmailVerificationFlow:
    def test_verify_email_marks_verified(self, client, app):
        from utils.email_verification import issue_verification_token
        u = make_user(email='verify@example.com', verified=False)
        raw = issue_verification_token(u)
        r = client.post('/api/auth/verify-email', json={'token': raw})
        assert r.status_code == 200
        assert User.query.get(u.id).email_verified is True

    def test_token_is_single_use(self, client):
        from utils.email_verification import issue_verification_token
        u = make_user(email='single@example.com', verified=False)
        raw = issue_verification_token(u)
        assert client.post('/api/auth/verify-email', json={'token': raw}).status_code == 200
        # reusing the burned token fails
        assert client.post('/api/auth/verify-email', json={'token': raw}).status_code == 400

    def test_bad_token_rejected(self, client):
        r = client.post('/api/auth/verify-email', json={'token': 'garbage'})
        assert r.status_code == 400


class TestBankGating:
    def test_unverified_cannot_create_link_token(self, client):
        u = make_user(email='unv@example.com', verified=False)
        from flask_jwt_extended import create_access_token
        headers = {'Authorization': f'Bearer {create_access_token(identity=str(u.id))}'}
        r = client.post('/api/plaid/create-link-token', headers=headers)
        assert r.status_code == 403
        assert r.get_json()['code'] == 'email_unverified'

    def test_verified_passes_the_gate(self, client, monkeypatch):
        u = make_user(email='ver@example.com', verified=True)
        from flask_jwt_extended import create_access_token
        headers = {'Authorization': f'Bearer {create_access_token(identity=str(u.id))}'}
        # stub the Plaid client so we test the gate, not Plaid
        import routes.plaid as plaid_routes
        from types import SimpleNamespace
        monkeypatch.setattr(plaid_routes, 'get_plaid_client',
                            lambda: SimpleNamespace(link_token_create=lambda req: SimpleNamespace(
                                to_dict=lambda: {'link_token': 'tok', 'expiration': 'x'})))
        r = client.post('/api/plaid/create-link-token', headers=headers)
        assert r.status_code != 403  # got past the verification gate


# ============================================================
# Area 3 — TOTP MFA
# ============================================================

class TestMfa:
    def _auth(self, user):
        from flask_jwt_extended import create_access_token
        return {'Authorization': f'Bearer {create_access_token(identity=str(user.id))}'}

    def test_setup_confirm_enables_mfa_and_returns_backup_codes(self, client):
        u = make_user(email='mfa@example.com')
        h = self._auth(u)
        setup = client.post('/api/auth/mfa/setup', headers=h).get_json()
        assert setup['secret'] and setup['qr_data_uri'].startswith('data:image/svg+xml')

        code = pyotp.TOTP(setup['secret']).now()
        confirm = client.post('/api/auth/mfa/confirm', headers=h, json={'code': code})
        assert confirm.status_code == 200
        assert len(confirm.get_json()['backup_codes']) == 10
        assert User.query.get(u.id).mfa_enabled is True

    def test_confirm_rejects_wrong_code(self, client):
        u = make_user(email='mfa2@example.com')
        h = self._auth(u)
        client.post('/api/auth/mfa/setup', headers=h)
        r = client.post('/api/auth/mfa/confirm', headers=h, json={'code': '000000'})
        assert r.status_code == 400
        assert User.query.get(u.id).mfa_enabled is False

    def test_login_requires_second_factor_when_enabled(self, client):
        u = make_user(email='mfa3@example.com', password='rightpass')
        h = self._auth(u)
        setup = client.post('/api/auth/mfa/setup', headers=h).get_json()
        client.post('/api/auth/mfa/confirm', headers=h, json={'code': pyotp.TOTP(setup['secret']).now()})

        # password step returns a pending token, NOT a session
        r = client.post('/api/auth/login', json={'email': 'mfa3@example.com', 'password': 'rightpass'})
        assert r.status_code == 200
        body = r.get_json()
        assert body.get('mfa_required') is True
        assert 'mfa_token' in body
        assert 'user' not in body  # no session issued yet

        # second step with a valid TOTP issues the session
        code = pyotp.TOTP(setup['secret']).now()
        r2 = client.post('/api/auth/login/mfa', json={'mfa_token': body['mfa_token'], 'code': code})
        assert r2.status_code == 200
        assert r2.get_json()['user']['email'] == 'mfa3@example.com'

    def test_login_mfa_rejects_bad_code(self, client):
        u = make_user(email='mfa4@example.com', password='rightpass')
        h = self._auth(u)
        setup = client.post('/api/auth/mfa/setup', headers=h).get_json()
        client.post('/api/auth/mfa/confirm', headers=h, json={'code': pyotp.TOTP(setup['secret']).now()})
        pending = client.post('/api/auth/login', json={'email': 'mfa4@example.com', 'password': 'rightpass'}).get_json()['mfa_token']
        r = client.post('/api/auth/login/mfa', json={'mfa_token': pending, 'code': '000000'})
        assert r.status_code == 401

    def test_backup_code_works_and_is_single_use(self, client):
        u = make_user(email='mfa5@example.com', password='rightpass')
        h = self._auth(u)
        setup = client.post('/api/auth/mfa/setup', headers=h).get_json()
        codes = client.post('/api/auth/mfa/confirm', headers=h,
                            json={'code': pyotp.TOTP(setup['secret']).now()}).get_json()['backup_codes']

        pending = client.post('/api/auth/login', json={'email': 'mfa5@example.com', 'password': 'rightpass'}).get_json()['mfa_token']
        r = client.post('/api/auth/login/mfa', json={'mfa_token': pending, 'code': codes[0]})
        assert r.status_code == 200
        # same backup code can't be reused
        pending2 = client.post('/api/auth/login', json={'email': 'mfa5@example.com', 'password': 'rightpass'}).get_json()['mfa_token']
        r2 = client.post('/api/auth/login/mfa', json={'mfa_token': pending2, 'code': codes[0]})
        assert r2.status_code == 401

    def test_disable_requires_password_and_code(self, client):
        u = make_user(email='mfa6@example.com', password='rightpass')
        h = self._auth(u)
        setup = client.post('/api/auth/mfa/setup', headers=h).get_json()
        client.post('/api/auth/mfa/confirm', headers=h, json={'code': pyotp.TOTP(setup['secret']).now()})

        # wrong password → refused
        assert client.post('/api/auth/mfa/disable', headers=h,
                           json={'password': 'nope', 'code': pyotp.TOTP(setup['secret']).now()}).status_code == 401
        # right password, wrong code → refused
        assert client.post('/api/auth/mfa/disable', headers=h,
                           json={'password': 'rightpass', 'code': '000000'}).status_code == 401
        # both correct → disabled, secret + backup codes wiped
        ok = client.post('/api/auth/mfa/disable', headers=h,
                         json={'password': 'rightpass', 'code': pyotp.TOTP(setup['secret']).now()})
        assert ok.status_code == 200
        fresh = User.query.get(u.id)
        assert fresh.mfa_enabled is False and fresh.mfa_secret is None
        assert MfaBackupCode.query.filter_by(user_id=u.id).count() == 0

    def test_totp_secret_encrypted_at_rest(self, client):
        u = make_user(email='mfa7@example.com')
        h = self._auth(u)
        setup = client.post('/api/auth/mfa/setup', headers=h).get_json()
        # the stored column is not the raw base32 secret
        stored = User.query.get(u.id).mfa_secret
        assert stored and stored != setup['secret']
