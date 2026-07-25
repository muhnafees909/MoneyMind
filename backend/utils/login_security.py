"""
Brute-force login protection: an email+IP hybrid lockout with escalating
cooldowns, plus a looser per-IP ceiling so one address can't spray many
accounts. Failures are logged for review; legitimate users are never
auto-banned for a few honest mistakes.
"""

import logging
from datetime import datetime, timedelta

from flask import request
from models.user import db
from models.login_security import LoginAttempt, LoginLockout

logger = logging.getLogger('moneymind.login')

# After this many consecutive fails on an (email, IP) pair, lock it.
FAIL_THRESHOLD = 5
# Escalating cooldown per lock level (seconds): 1m, 5m, 15m, then 1h capped.
COOLDOWN_SCHEDULE = [60, 300, 900, 3600]
# A single fail streak resets after this much quiet time.
STREAK_RESET_AFTER = timedelta(minutes=30)

# Per-IP ceiling: too many failures from one IP across ANY accounts in the
# window → block that IP briefly (stops account spraying).
IP_WINDOW = timedelta(minutes=15)
IP_FAIL_CEILING = 20
IP_BLOCK_SECONDS = 900  # 15m


def client_ip():
    """Best-effort client IP. Behind Render/other proxies the real client is
    the first hop in X-Forwarded-For; fall back to the socket address."""
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _cooldown_seconds(lock_level):
    idx = min(max(lock_level, 1), len(COOLDOWN_SCHEDULE)) - 1
    return COOLDOWN_SCHEDULE[idx]


def _get_or_create_lockout(email, ip):
    row = LoginLockout.query.filter_by(email=email, ip=ip).first()
    if row is None:
        row = LoginLockout(email=email, ip=ip, fail_count=0, lock_level=0)
        db.session.add(row)
    return row


def _humanize(seconds):
    if seconds >= 3600:
        h = round(seconds / 3600)
        return f'{h} hour' + ('s' if h != 1 else '')
    minutes = max(1, round(seconds / 60))
    return f'{minutes} minute' + ('s' if minutes != 1 else '')


def check_locked(email, ip):
    """Return (locked: bool, message: str|None, retry_after_seconds: int).
    Call before verifying credentials."""
    now = datetime.utcnow()

    # Per-IP ceiling first (cheap guard against spraying)
    ip_fails = LoginAttempt.query.filter(
        LoginAttempt.ip == ip,
        LoginAttempt.successful.is_(False),
        LoginAttempt.created_at >= now - IP_WINDOW,
    ).count()
    if ip_fails >= IP_FAIL_CEILING:
        return True, (
            'Too many failed sign-in attempts from your network. '
            f'Please try again in about {_humanize(IP_BLOCK_SECONDS)}.'
        ), IP_BLOCK_SECONDS

    row = LoginLockout.query.filter_by(email=email, ip=ip).first()
    if row and row.locked_until and row.locked_until > now:
        retry = int((row.locked_until - now).total_seconds())
        return True, (
            'Too many failed attempts. This account is temporarily locked — '
            f'try again in about {_humanize(retry)}.'
        ), retry
    return False, None, 0


def record_failure(email, ip):
    """Log a failed attempt and advance the lockout state for (email, IP)."""
    now = datetime.utcnow()
    db.session.add(LoginAttempt(email=email, ip=ip, successful=False, created_at=now))

    row = _get_or_create_lockout(email, ip)
    # Reset a stale streak (quiet gap since last failure)
    if row.updated_at and now - row.updated_at > STREAK_RESET_AFTER and \
            (not row.locked_until or row.locked_until <= now):
        row.fail_count = 0
    row.fail_count += 1

    if row.fail_count >= FAIL_THRESHOLD:
        row.lock_level += 1
        cooldown = _cooldown_seconds(row.lock_level)
        row.locked_until = now + timedelta(seconds=cooldown)
        row.fail_count = 0
        logger.warning(
            '[LOGIN LOCKOUT] email=%s ip=%s level=%s cooldown=%ss',
            email, ip, row.lock_level, cooldown
        )
    db.session.commit()


def record_success(email, ip):
    """A good sign-in clears the streak/lock for this (email, IP)."""
    db.session.add(LoginAttempt(email=email, ip=ip, successful=True,
                                created_at=datetime.utcnow()))
    row = LoginLockout.query.filter_by(email=email, ip=ip).first()
    if row:
        row.fail_count = 0
        row.lock_level = 0
        row.locked_until = None
    db.session.commit()
