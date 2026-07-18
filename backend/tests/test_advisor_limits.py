"""
AI advisor rate limiting, usage accounting, and abuse-flag tests.

All requests go straight at the Flask API with a raw JWT (the test client
never touches the Angular frontend), so passing tests prove the limits are
enforced server-side and can't be bypassed by skipping the UI.
OpenAI is always mocked — no test spends money.
"""

from datetime import datetime, timedelta

import pytest

import routes.chat as chat_routes
import utils.advisor_limits as limits
from models.advisor_usage import AdvisorUsage, AdvisorAbuseFlag
from models.user import db


@pytest.fixture
def mock_ai(monkeypatch):
    """Replace the OpenAI call; returns the list of messages that got through."""
    forwarded = []

    def fake_send_message(user_id, message, history=None):
        forwarded.append(message)
        return {
            'response': 'Here is some advice.',
            'context_used': {'model_used': 'mock'},
            'error': None
        }

    monkeypatch.setattr(chat_routes, 'send_message', fake_send_message)
    return forwarded


@pytest.fixture
def set_limits(monkeypatch):
    """Override limits for a test: set_limits(per_minute=…, per_day=…)."""
    def _set(per_minute=None, per_day=None, max_chars=None):
        if per_minute is not None:
            monkeypatch.setattr(limits, 'LIMIT_PER_MINUTE', per_minute)
        if per_day is not None:
            monkeypatch.setattr(limits, 'LIMIT_PER_DAY', per_day)
        if max_chars is not None:
            monkeypatch.setattr(limits, 'MAX_MESSAGE_CHARS', max_chars)
    return _set


def ask(client, headers, message='How am I doing this month?', history=None):
    payload = {'message': message}
    if history is not None:
        payload['history'] = history
    return client.post('/api/chat/message', headers=headers, json=payload)


class TestPerMinuteLimit:
    def test_burst_over_limit_rejected(self, client, auth_headers, user, mock_ai, set_limits):
        set_limits(per_minute=3, per_day=100)

        for i in range(3):
            assert ask(client, auth_headers, f'question {i}').status_code == 200

        resp = ask(client, auth_headers, 'one too many')
        assert resp.status_code == 429
        body = resp.get_json()
        assert body['error_code'] == 'ADVISOR_RATE_LIMIT'
        assert 'per minute' in body['error']
        assert 1 <= body['retry_after_seconds'] <= 60
        assert resp.headers['Retry-After'] == str(body['retry_after_seconds'])
        # The rejected request never reached OpenAI
        assert len(mock_ai) == 3

    def test_rejected_requests_do_not_consume_quota(self, client, auth_headers, user,
                                                    mock_ai, set_limits):
        set_limits(per_minute=2, per_day=100)
        ask(client, auth_headers, 'q1')
        ask(client, auth_headers, 'q2')
        ask(client, auth_headers, 'rejected')  # 429

        usage = client.get('/api/chat/usage', headers=auth_headers).get_json()
        assert usage['daily']['used'] == 2  # the 429'd attempt doesn't count


class TestDailyLimit:
    def test_daily_cap_rejected_with_reset_time(self, client, auth_headers, user,
                                                mock_ai, set_limits):
        set_limits(per_minute=100, per_day=5)

        for i in range(5):
            assert ask(client, auth_headers, f'question {i}').status_code == 200

        resp = ask(client, auth_headers, 'past the cap')
        assert resp.status_code == 429
        body = resp.get_json()
        assert body['error_code'] == 'ADVISOR_DAILY_LIMIT'
        assert 'daily advisor limit of 5 messages' in body['error']
        assert 'Resets in' in body['error']
        assert 0 < body['retry_after_seconds'] <= 86400
        assert body['usage']['daily']['remaining'] == 0
        assert len(mock_ai) == 5

    def test_yesterdays_usage_does_not_count(self, client, auth_headers, user,
                                             mock_ai, set_limits, app):
        set_limits(per_minute=100, per_day=2)
        # two messages yesterday (UTC) — today's quota must be untouched
        yesterday = datetime.utcnow() - timedelta(days=1)
        for _ in range(2):
            db.session.add(AdvisorUsage(user_id=user.id, message_hash='x' * 64,
                                        message_chars=10, was_limited=False,
                                        created_at=yesterday))
        db.session.commit()

        assert ask(client, auth_headers).status_code == 200


class TestServerSideEnforcement:
    def test_direct_api_call_cannot_bypass_limits(self, client, auth_headers, user,
                                                  mock_ai, set_limits):
        """Simulates a scripted client hitting the API directly with a valid JWT."""
        set_limits(per_minute=100, per_day=1)
        assert ask(client, auth_headers).status_code == 200

        # No frontend involved: raw POST with auth headers still gets refused
        resp = client.post('/api/chat/message', headers=auth_headers,
                           json={'message': 'scripted request'})
        assert resp.status_code == 429
        assert len(mock_ai) == 1

    def test_unauthenticated_request_rejected(self, client, mock_ai):
        resp = client.post('/api/chat/message', json={'message': 'hi'})
        assert resp.status_code == 401
        assert len(mock_ai) == 0


class TestInputCaps:
    def test_oversized_message_rejected(self, client, auth_headers, user, mock_ai):
        resp = ask(client, auth_headers, 'x' * (limits.MAX_MESSAGE_CHARS + 1))
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['error_code'] == 'MESSAGE_TOO_LONG'
        assert len(mock_ai) == 0

    def test_oversized_history_entry_rejected(self, client, auth_headers, user, mock_ai):
        history = [{'role': 'user', 'content': 'x' * (limits.MAX_MESSAGE_CHARS + 1)}]
        resp = ask(client, auth_headers, history=history)
        assert resp.status_code == 400
        assert len(mock_ai) == 0

    def test_too_many_history_entries_rejected(self, client, auth_headers, user, mock_ai):
        history = [{'role': 'user', 'content': 'hi'}] * (limits.MAX_HISTORY_ENTRIES + 1)
        resp = ask(client, auth_headers, history=history)
        assert resp.status_code == 400
        assert resp.get_json()['error_code'] == 'HISTORY_TOO_LONG'
        assert len(mock_ai) == 0


class TestUsageEndpoint:
    def test_reports_remaining_and_reset(self, client, auth_headers, user,
                                         mock_ai, set_limits):
        set_limits(per_minute=10, per_day=50)
        usage = client.get('/api/chat/usage', headers=auth_headers).get_json()
        assert usage['daily'] == {'limit': 50, 'used': 0, 'remaining': 50,
                                  'resets_in_seconds': usage['daily']['resets_in_seconds']}
        assert 0 < usage['daily']['resets_in_seconds'] <= 86400

        ask(client, auth_headers, 'q1')
        ask(client, auth_headers, 'q2')
        usage = client.get('/api/chat/usage', headers=auth_headers).get_json()
        assert usage['daily']['used'] == 2
        assert usage['daily']['remaining'] == 48
        assert usage['minute']['used'] == 2

    def test_success_response_includes_usage(self, client, auth_headers, user,
                                             mock_ai, set_limits):
        set_limits(per_minute=10, per_day=50)
        body = ask(client, auth_headers).get_json()
        assert body['usage']['daily']['used'] == 1
        assert body['usage']['daily']['remaining'] == 49


class TestAbuseFlags:
    def test_repeated_identical_messages_flagged_once(self, client, auth_headers, user,
                                                      mock_ai, set_limits):
        set_limits(per_minute=100, per_day=100)
        # Same message with case/whitespace variations — normalization catches it
        variants = ['Am I rich?', 'am i  rich?', 'AM I RICH?', ' am i rich? ',
                    'Am I rich?', 'am i rich?']
        for v in variants:
            ask(client, auth_headers, v)

        flags = AdvisorAbuseFlag.query.filter_by(
            user_id=user.id, reason='repeated_identical_messages').all()
        assert len(flags) == 1  # deduped, not one flag per repeat

    def test_limit_hits_across_days_flagged(self, client, auth_headers, user,
                                            mock_ai, set_limits):
        set_limits(per_minute=1, per_day=100)
        # Backdated limit-hit rows on three separate days this week
        for days_ago in (1, 2, 3):
            db.session.add(AdvisorUsage(
                user_id=user.id, message_hash='y' * 64, message_chars=5,
                was_limited=True, limit_kind='minute',
                created_at=datetime.utcnow() - timedelta(days=days_ago)))
        db.session.commit()

        ask(client, auth_headers, 'q1')       # consumes the 1/minute quota
        ask(client, auth_headers, 'blocked')  # 429 → triggers the pattern check

        flags = AdvisorAbuseFlag.query.filter_by(
            user_id=user.id, reason='repeated_limit_hits').all()
        assert len(flags) == 1

    def test_advisor_only_account_flagged(self, client, auth_headers, user,
                                          mock_ai, set_limits):
        set_limits(per_minute=100, per_day=100)
        # Fixture user has no transactions/budgets/goals/banks — three advisor
        # messages from such an account is the flag threshold
        for i in range(3):
            ask(client, auth_headers, f'unique question {i}')

        flags = AdvisorAbuseFlag.query.filter_by(
            user_id=user.id, reason='advisor_only_account').all()
        assert len(flags) == 1

    def test_account_with_real_usage_not_flagged(self, client, auth_headers, user,
                                                 account, mock_ai, set_limits):
        set_limits(per_minute=100, per_day=100)
        # `account` fixture links a bank — this is a legitimate user
        for i in range(4):
            ask(client, auth_headers, f'unique question {i}')

        assert AdvisorAbuseFlag.query.filter_by(
            user_id=user.id, reason='advisor_only_account').count() == 0
