"""
Brute-force login protection state.

Two tables:
  - login_attempts: an append-only log of failed sign-ins (email + IP), for
    later review. Never auto-bans; it's evidence, not enforcement.
  - login_lockouts: current failure streak + escalating cooldown, keyed on the
    (email, IP) pair (the hybrid strategy) so an attacker on one IP can't lock a
    legitimate user out from elsewhere. A separate per-IP ceiling in the route
    stops one IP spraying many accounts.
"""

from datetime import datetime
from models.user import db


class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=True, index=True)   # lowercased; may be unknown
    ip = db.Column(db.String(45), nullable=True, index=True)       # IPv4/IPv6
    successful = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class LoginLockout(db.Model):
    """Live lockout state for one (email, IP) pair."""
    __tablename__ = 'login_lockouts'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    ip = db.Column(db.String(45), nullable=False)
    # consecutive fails since the last success or lock
    fail_count = db.Column(db.Integer, nullable=False, default=0)
    # how many times this pair has been locked (drives escalating cooldowns)
    lock_level = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('email', 'ip', name='uq_login_lockout_email_ip'),
        db.Index('ix_login_lockout_email_ip', 'email', 'ip'),
    )
