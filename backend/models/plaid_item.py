from datetime import datetime
from models.user import db
from utils.token_crypto import encrypt_token, decrypt_token


class PlaidItem(db.Model):
    """Store Plaid item credentials and metadata for each connected bank account"""
    __tablename__ = 'plaid_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.String(255), unique=True, nullable=False)
    access_token = db.Column(db.String(500), nullable=False)  # Fernet-encrypted at rest
    institution_name = db.Column(db.String(255), nullable=True)
    last_sync_timestamp = db.Column(db.DateTime, nullable=True)
    sync_cursor = db.Column(db.String(255), nullable=True)  # transactions_sync incremental cursor
    # Item-error state: set when Plaid reports the connection needs the user to
    # act (e.g. ITEM_LOGIN_REQUIRED). Cleared automatically on the next
    # successful sync. Drives the "reconnect" prompt on Accounts/Envelopes.
    needs_reauth = db.Column(db.Boolean, nullable=False, default=False)
    last_error_code = db.Column(db.String(60), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_access_token(self, token: str):
        self.access_token = encrypt_token(token)

    def get_access_token(self) -> str:
        return decrypt_token(self.access_token)

    # Relationship to User
    user = db.relationship('User', backref=db.backref('plaid_items', lazy=True))

    def __repr__(self):
        return f'<PlaidItem {self.item_id} for User {self.user_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'item_id': self.item_id,
            'institution_name': self.institution_name,
            'last_sync_timestamp': self.last_sync_timestamp.isoformat() if self.last_sync_timestamp else None,
            'needs_reauth': self.needs_reauth,
            'last_error_code': self.last_error_code,
            'created_at': self.created_at.isoformat()
        }
