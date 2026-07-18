"""
Server-side rate limiting, usage accounting, and lightweight abuse-pattern
detection for the AI advisor.

Every advisor call costs real money (OpenAI API), so limits are enforced
here — never trust the client. Counters are derived from the advisor_usage
table so they survive restarts and hold across gunicorn workers.

Configuration (env vars, all optional):
    ADVISOR_LIMIT_PER_MINUTE   burst cap, default 10
    ADVISOR_LIMIT_PER_DAY      daily cost cap, default 50 (UTC calendar day)
    ADVISOR_MAX_MESSAGE_CHARS  per-message length cap, default 4000
"""

import hashlib
import logging
import os
import re
from datetime import datetime, timedelta

from models.advisor_usage import AdvisorUsage, AdvisorAbuseFlag
from models.user import db

logger = logging.getLogger('moneymind.advisor')

# Read at import; tests override the module attributes directly.
LIMIT_PER_MINUTE = int(os.getenv('ADVISOR_LIMIT_PER_MINUTE', '10'))
LIMIT_PER_DAY = int(os.getenv('ADVISOR_LIMIT_PER_DAY', '50'))
MAX_MESSAGE_CHARS = int(os.getenv('ADVISOR_MAX_MESSAGE_CHARS', '4000'))
MAX_HISTORY_ENTRIES = 20

# Abuse-review thresholds (deliberately loose — flags are for a human, not a ban)
DUPLICATE_MSGS_PER_HOUR = 5       # same normalized message this many times in an hour
LIMIT_HIT_DAYS_IN_WEEK = 3        # days (of last 7) on which the user hit a limit
ADVISOR_ONLY_MIN_MESSAGES = 3     # advisor messages from an account with no other usage


def normalized_hash(message):
    """Hash of the message with case/whitespace noise removed."""
    normalized = re.sub(r'\s+', ' ', message.strip().lower())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _format_duration(seconds):
    """Human-friendly duration for limit messages ('6h 12m', '45m', 'under a minute')."""
    if seconds < 60:
        return 'under a minute'
    hours, rem = divmod(int(seconds), 3600)
    minutes = rem // 60
    if hours and minutes:
        return f'{hours}h {minutes}m'
    if hours:
        return f'{hours}h'
    return f'{minutes}m'


def _seconds_until_day_reset(now):
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def _counted(user_id):
    """Base query for rows that consume quota (rejected attempts don't)."""
    return AdvisorUsage.query.filter(
        AdvisorUsage.user_id == user_id,
        AdvisorUsage.was_limited.is_(False)
    )


def usage_snapshot(user_id, now=None):
    """Current usage vs. limits — powers the in-UI indicator and 429 payloads."""
    now = now or datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    minute_used = _counted(user_id).filter(
        AdvisorUsage.created_at >= now - timedelta(seconds=60)).count()
    day_used = _counted(user_id).filter(AdvisorUsage.created_at >= day_start).count()
    return {
        'minute': {
            'limit': LIMIT_PER_MINUTE,
            'used': minute_used,
            'remaining': max(0, LIMIT_PER_MINUTE - minute_used)
        },
        'daily': {
            'limit': LIMIT_PER_DAY,
            'used': day_used,
            'remaining': max(0, LIMIT_PER_DAY - day_used),
            'resets_in_seconds': _seconds_until_day_reset(now)
        }
    }


def check_limits(user_id, message):
    """
    Returns None when the request may proceed, else a dict describing the
    limit that was hit:
        {'error_code', 'message', 'retry_after_seconds'}

    A rejected attempt is recorded (was_limited=True) for abuse review but
    does not consume quota.
    """
    now = datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    hit = None

    day_used = _counted(user_id).filter(AdvisorUsage.created_at >= day_start).count()
    if day_used >= LIMIT_PER_DAY:
        reset_s = _seconds_until_day_reset(now)
        hit = {
            'error_code': 'ADVISOR_DAILY_LIMIT',
            'message': (
                f"You've reached your daily advisor limit of {LIMIT_PER_DAY} messages. "
                f"Resets in {_format_duration(reset_s)}."
            ),
            'retry_after_seconds': reset_s,
            'limit_kind': 'day'
        }
    else:
        window_start = now - timedelta(seconds=60)
        in_window = (_counted(user_id)
                     .filter(AdvisorUsage.created_at >= window_start)
                     .order_by(AdvisorUsage.created_at.asc())
                     .all())
        if len(in_window) >= LIMIT_PER_MINUTE:
            oldest = in_window[0].created_at
            retry_s = max(1, 60 - int((now - oldest).total_seconds()))
            hit = {
                'error_code': 'ADVISOR_RATE_LIMIT',
                'message': (
                    f"That's a lot of questions at once — the advisor accepts "
                    f"{LIMIT_PER_MINUTE} messages per minute. Try again in about "
                    f"{retry_s} seconds."
                ),
                'retry_after_seconds': retry_s,
                'limit_kind': 'minute'
            }

    if hit:
        db.session.add(AdvisorUsage(
            user_id=user_id,
            message_hash=normalized_hash(message),
            message_chars=len(message),
            was_limited=True,
            limit_kind=hit['limit_kind']
        ))
        db.session.commit()
        _flag_repeated_limit_hits(user_id, now)
        return {k: hit[k] for k in ('error_code', 'message', 'retry_after_seconds')}

    return None


def record_usage(user_id, message):
    """
    Record an accepted request (consumes quota), then run the cheap
    abuse-pattern checks. Called before the OpenAI request so a crash
    mid-call still counts the attempt.
    """
    now = datetime.utcnow()
    msg_hash = normalized_hash(message)
    db.session.add(AdvisorUsage(
        user_id=user_id,
        message_hash=msg_hash,
        message_chars=len(message),
        was_limited=False
    ))
    db.session.commit()

    _flag_duplicate_messages(user_id, msg_hash, now)
    _flag_advisor_only_account(user_id)


# ---------------------------------------------------------------------------
# Abuse-pattern detection — log for review, never auto-ban. False positives
# cost a legitimate user's trust; a human looks at these flags.
# ---------------------------------------------------------------------------

def _maybe_flag(user_id, reason, details, dedupe_hours):
    """Insert a flag unless the same reason was already flagged recently."""
    since = datetime.utcnow() - timedelta(hours=dedupe_hours)
    exists = AdvisorAbuseFlag.query.filter(
        AdvisorAbuseFlag.user_id == user_id,
        AdvisorAbuseFlag.reason == reason,
        AdvisorAbuseFlag.created_at >= since
    ).first()
    if exists:
        return
    db.session.add(AdvisorAbuseFlag(user_id=user_id, reason=reason, details=details))
    db.session.commit()
    logger.warning('[ADVISOR ABUSE] user=%s reason=%s details=%s', user_id, reason, details)


def _flag_repeated_limit_hits(user_id, now):
    """User keeps slamming into rate limits across multiple days this week."""
    since = now - timedelta(days=7)
    rows = (AdvisorUsage.query
            .filter(AdvisorUsage.user_id == user_id,
                    AdvisorUsage.was_limited.is_(True),
                    AdvisorUsage.created_at >= since)
            .all())
    days = {r.created_at.date() for r in rows}
    if len(days) >= LIMIT_HIT_DAYS_IN_WEEK:
        _maybe_flag(
            user_id, 'repeated_limit_hits',
            f'hit advisor rate limits on {len(days)} of the last 7 days',
            dedupe_hours=7 * 24
        )


def _flag_duplicate_messages(user_id, msg_hash, now):
    """Near-identical message repeated rapidly — smells scripted."""
    count = _counted(user_id).filter(
        AdvisorUsage.message_hash == msg_hash,
        AdvisorUsage.created_at >= now - timedelta(hours=1)
    ).count()
    if count >= DUPLICATE_MSGS_PER_HOUR:
        _maybe_flag(
            user_id, 'repeated_identical_messages',
            f'same normalized message {count}x in the last hour (hash {msg_hash[:12]}…)',
            dedupe_hours=24
        )


def _flag_advisor_only_account(user_id):
    """
    Account uses the advisor but nothing else in the app — no transactions,
    budgets, goals, or linked banks. Legitimate users almost always have at
    least one of these before (or soon after) chatting.
    """
    total_messages = _counted(user_id).count()
    if total_messages < ADVISOR_ONLY_MIN_MESSAGES:
        return

    # Imported here to avoid circular imports at module load
    from models.budget import Budget
    from models.goal import FinancialGoal
    from models.plaid_item import PlaidItem
    from models.transaction import Transaction

    for model in (Transaction, Budget, FinancialGoal, PlaidItem):
        if model.query.filter_by(user_id=user_id).first() is not None:
            return

    _maybe_flag(
        user_id, 'advisor_only_account',
        f'{total_messages} advisor messages from an account with no transactions, '
        'budgets, goals, or linked banks',
        dedupe_hours=24
    )
