"""
Advisor request log — one row per attempt against the AI advisor.

This table is the single source of truth for rate limiting, the in-UI
usage indicator, and abuse-pattern review. It lives in the shared
database (not per-process memory) so limits hold across gunicorn
workers and server restarts.
"""

from datetime import datetime

from models.user import db


class AdvisorUsage(db.Model):
    __tablename__ = 'advisor_usage'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    # sha256 of the normalized message (lowercased, whitespace-collapsed) —
    # lets abuse review spot repeated identical messages without storing them
    message_hash = db.Column(db.String(64), nullable=False)
    message_chars = db.Column(db.Integer, nullable=False, default=0)
    # True when the request was rejected by our limiter (these rows do NOT
    # count against quotas — they exist for abuse-pattern review)
    was_limited = db.Column(db.Boolean, nullable=False, default=False)
    limit_kind = db.Column(db.String(10), nullable=True)  # 'minute' | 'day'


class AdvisorAbuseFlag(db.Model):
    """A pattern worth a human look. Never blocks the user by itself."""
    __tablename__ = 'advisor_abuse_flags'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    reason = db.Column(db.String(40), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
