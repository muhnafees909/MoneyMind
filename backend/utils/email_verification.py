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
    """Build the link and hand off to the (pluggable) transport."""
    link = f'{FRONTEND_BASE}/verify-email?token={raw_token}'
    subject = 'Confirm your MoneyMind email'
    body = (
        f'Hi {user.first_name or "there"},\n\n'
        'Confirm your email to unlock bank connections on MoneyMind:\n'
        f'{link}\n\n'
        'This link expires in 24 hours. If you didn’t create an account, ignore this email.'
    )
    send_email(user.email, subject, body, link=link)


def send_email(to_email, subject, body, link=None):
    """
    Pluggable transport. No provider is configured in this project yet, so the
    default implementation LOGS the message (and the link) — the verification
    flow is fully functional in dev. To go live, set the provider env vars and
    replace this body with the actual send (SMTP / SendGrid / SES / …).
    """
    provider = os.getenv('EMAIL_PROVIDER', '').lower()
    if not provider:
        logger.info(
            '[EMAIL:DEV] would send to=%s subject=%r link=%s',
            to_email, subject, link or '(none)'
        )
        # Also print so it’s visible in the dev server console
        print(f'[EMAIL:DEV] to={to_email} subject={subject!r}\n  link={link}')
        return

    # e.g. elif provider == 'smtp': ...  / 'sendgrid': ...
    raise NotImplementedError(
        f'EMAIL_PROVIDER={provider!r} is set but no transport is implemented yet.'
    )
