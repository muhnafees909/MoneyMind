import bcrypt
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash  # legacy pbkdf2 verification only

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # --- Email verification ---
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    # sha256 of the current single-use verification token (never the raw token)
    verification_token_hash = db.Column(db.String(64), nullable=True, index=True)
    verification_sent_at = db.Column(db.DateTime, nullable=True)

    # --- TOTP MFA ---
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    # Fernet-encrypted TOTP secret (like Plaid tokens); null until enrolled
    mfa_secret = db.Column(db.String(255), nullable=True)

    backup_codes = db.relationship(
        'MfaBackupCode', backref='user', lazy=True, cascade='all, delete-orphan'
    )

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

    def check_password(self, password):
        # New hashes are bcrypt ($2…); older accounts may still hold
        # werkzeug pbkdf2 hashes — verify those too, and let the login
        # route transparently rehash them to bcrypt on success.
        if self.password_hash.startswith('$2'):
            try:
                return bcrypt.checkpw(
                    password.encode('utf-8'), self.password_hash.encode('utf-8')
                )
            except ValueError:
                return False
        return check_password_hash(self.password_hash, password)

    @property
    def password_needs_rehash(self):
        return not self.password_hash.startswith('$2')

    def __repr__(self):
        return f"User('{self.email}', '{self.first_name}')"


class MfaBackupCode(db.Model):
    """One-time recovery code for MFA. Stored as a bcrypt hash — the raw codes
    are shown to the user exactly once at generation time."""
    __tablename__ = 'mfa_backup_codes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
