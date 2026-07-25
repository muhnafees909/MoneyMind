"""
Email verification: single-use, time-limited tokens plus a pluggable sender.

Delivery is intentionally abstracted behind send_email(): in dev (no provider
configured) it just logs the verification link so the whole flow works
end-to-end. Wiring a real provider later means implementing one function —
nothing else changes.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta

from models.user import db

logger = logging.getLogger('moneymind.email')

TOKEN_TTL = timedelta(hours=24)
# Where the verification link should point (the SPA route that calls /verify)
FRONTEND_BASE = os.getenv('FRONTEND_BASE_URL', 'http://localhost:4200')


def _hash_token(raw):
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def issue_verification_token(user):
    """Generate a fresh single-use token, store only its hash on the user, and
    return the raw token (to embed in the emailed link)."""
    raw = secrets.token_urlsafe(32)
    user.verification_token_hash = _hash_token(raw)
    user.verification_sent_at = datetime.utcnow()
    db.session.commit()
    return raw


def verify_token(raw):
    """Consume a token. Returns (user, None) on success or (None, error)."""
    if not raw:
        return None, 'Missing verification token.'
    from models.user import User
    user = User.query.filter_by(verification_token_hash=_hash_token(raw)).first()
    if not user:
        return None, 'This verification link is invalid or has already been used.'
    if not user.verification_sent_at or \
            datetime.utcnow() - user.verification_sent_at > TOKEN_TTL:
        return None, 'This verification link has expired. Request a new one.'

    user.email_verified = True
    user.verification_token_hash = None  # single-use: burn it
    user.verification_sent_at = None
    db.session.commit()
    return user, None


def send_verification_email(user, raw_token):
    """Build the link + message and hand off to the (pluggable) transport."""
    link = f'{FRONTEND_BASE}/verify-email?token={raw_token}'
    name = user.first_name or 'there'
    subject = 'Confirm your MoneyMind email'
    text_body = (
        f'Hi {name},\n\n'
        'Confirm your email to unlock bank connections on MoneyMind:\n'
        f'{link}\n\n'
        'This link expires in 24 hours. If you didn’t create an account, ignore this email.'
    )
    html_body = _verification_html(name, link)
    send_email(user.email, subject, text_body, html_body=html_body, link=link)


def _verification_html(name, link):
    """A small, self-contained branded HTML email (no external assets)."""
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;background:#f5f2ec;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#2b2723;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#fffdf9;border-radius:14px;padding:36px 32px;border:1px solid #e7e0d5;">
          <tr><td style="font-size:20px;font-weight:700;letter-spacing:-0.01em;padding-bottom:20px;">MoneyMind</td></tr>
          <tr><td style="font-size:16px;line-height:1.55;padding-bottom:8px;">Hi {name},</td></tr>
          <tr><td style="font-size:16px;line-height:1.55;padding-bottom:24px;">
            Confirm your email to unlock bank connections and secure your account.
          </td></tr>
          <tr><td style="padding-bottom:28px;">
            <a href="{link}" style="display:inline-block;background:#2b2723;color:#fffdf9;text-decoration:none;font-size:15px;font-weight:600;padding:12px 24px;border-radius:10px;">
              Confirm email
            </a>
          </td></tr>
          <tr><td style="font-size:13px;line-height:1.5;color:#86817a;padding-bottom:6px;">
            Or paste this link into your browser:
          </td></tr>
          <tr><td style="font-size:13px;line-height:1.5;word-break:break-all;padding-bottom:24px;">
            <a href="{link}" style="color:#6c6157;">{link}</a>
          </td></tr>
          <tr><td style="font-size:12px;line-height:1.5;color:#a49c90;border-top:1px solid #eee6d9;padding-top:18px;">
            This link expires in 24 hours. If you didn’t create a MoneyMind account, you can safely ignore this email.
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def send_email(to_email, subject, body, html_body=None, link=None):
    """
    Pluggable transport. Delegates to utils.email_transport, which picks a
    provider from EMAIL_PROVIDER (Resend in prod; console-logging in dev).

    Raises on failure so callers (register/resend) can decide how to react —
    the register flow treats a send failure as non-fatal, resend surfaces it.
    """
    from utils import email_transport
    ok, error = email_transport.send(to_email, subject, body, html_body=html_body, link=link)
    if not ok:
        raise RuntimeError(error or 'Email send failed.')
