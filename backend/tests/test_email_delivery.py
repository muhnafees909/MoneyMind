"""
Email delivery tests: the transport picks the right provider, the Resend path
calls the SDK correctly (mocked — never a real network call), and the token
lifecycle (issue → verify → burn → expire) stays intact.
"""

import sys
import types
from datetime import datetime, timedelta

import pytest

from models.user import db, User
from utils import email_transport
from utils.email_verification import (
    issue_verification_token, send_verification_email, verify_token,
)


# ---------------------------------------------------------------- transport --

def test_dev_mode_logs_and_succeeds(monkeypatch, capsys):
    """No EMAIL_PROVIDER set -> dev mode: no network, prints the link, ok=True."""
    monkeypatch.delenv('EMAIL_PROVIDER', raising=False)
    ok, error = email_transport.send(
        'user@example.com', 'Subject', 'text body', link='http://x/verify?token=abc'
    )
    assert ok is True
    assert error is None
    assert 'http://x/verify?token=abc' in capsys.readouterr().out


def test_resend_missing_key_fails_soft(monkeypatch):
    """EMAIL_PROVIDER=resend but no API key -> ok=False, no exception."""
    monkeypatch.setenv('EMAIL_PROVIDER', 'resend')
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
    ok, error = email_transport.send('user@example.com', 'S', 'body')
    assert ok is False
    assert error


def test_resend_sends_with_correct_params(monkeypatch):
    """EMAIL_PROVIDER=resend -> calls resend.Emails.send with from/to/subject/html."""
    monkeypatch.setenv('EMAIL_PROVIDER', 'resend')
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')
    monkeypatch.setenv('EMAIL_FROM', 'MoneyMind <noreply@test.dev>')

    sent = {}
    fake_resend = types.ModuleType('resend')
    fake_resend.api_key = None
    fake_resend.Emails = types.SimpleNamespace(
        send=lambda params: sent.update(params) or {'id': 'msg-123'}
    )
    monkeypatch.setitem(sys.modules, 'resend', fake_resend)

    ok, error = email_transport.send(
        'user@example.com', 'Confirm', 'text', html_body='<b>hi</b>'
    )
    assert ok is True
    assert error is None
    assert sent['from'] == 'MoneyMind <noreply@test.dev>'
    assert sent['to'] == ['user@example.com']
    assert sent['subject'] == 'Confirm'
    assert sent['text'] == 'text'
    assert sent['html'] == '<b>hi</b>'


def test_resend_sdk_exception_fails_soft(monkeypatch):
    """A provider exception is swallowed into ok=False, never propagated."""
    monkeypatch.setenv('EMAIL_PROVIDER', 'resend')
    monkeypatch.setenv('RESEND_API_KEY', 'test-key')

    def boom(_params):
        raise RuntimeError('provider down')

    fake_resend = types.ModuleType('resend')
    fake_resend.api_key = None
    fake_resend.Emails = types.SimpleNamespace(send=boom)
    monkeypatch.setitem(sys.modules, 'resend', fake_resend)

    ok, error = email_transport.send('user@example.com', 'S', 'body')
    assert ok is False
    assert error


# ------------------------------------------------------------ token lifecycle --

def test_send_verification_email_builds_html(monkeypatch, app):
    """send_verification_email passes a branded HTML body through to transport."""
    captured = {}

    def fake_send(to, subject, text, html_body=None, link=None):
        captured.update(to=to, subject=subject, html=html_body, link=link)
        return True, None

    monkeypatch.setattr(email_transport, 'send', fake_send)

    with app.app_context():
        u = User(email='new@example.com', first_name='Sam')
        u.set_password('password123')
        db.session.add(u)
        db.session.commit()
        raw = issue_verification_token(u)
        send_verification_email(u, raw)

    assert captured['to'] == 'new@example.com'
    assert 'MoneyMind' in captured['html']
    assert raw in captured['link']
    assert 'Sam' in captured['html']


def test_verify_token_is_single_use(app):
    with app.app_context():
        u = User(email='v@example.com', first_name='V')
        u.set_password('password123')
        db.session.add(u)
        db.session.commit()
        raw = issue_verification_token(u)

        user, error = verify_token(raw)
        assert error is None
        assert user.email_verified is True

        # Second use fails — the token was burned.
        user2, error2 = verify_token(raw)
        assert user2 is None
        assert error2


def test_verify_token_expired(app):
    with app.app_context():
        u = User(email='e@example.com', first_name='E')
        u.set_password('password123')
        db.session.add(u)
        db.session.commit()
        raw = issue_verification_token(u)
        # Age the token past the 24h TTL.
        u.verification_sent_at = datetime.utcnow() - timedelta(hours=25)
        db.session.commit()

        user, error = verify_token(raw)
        assert user is None
        assert 'expired' in error.lower()
