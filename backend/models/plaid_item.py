from datetime import datetime
from models.user import db


class PlaidItem(db.Model):
    """Store Plaid item credentials and metadata for each connected bank account"""
    __tablename__ = 'plaid_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.String(255), unique=True, nullable=False)
    access_token = db.Column(db.String(500), nullable=False)  # Encrypted in production
    institution_name = db.Column(db.String(255), nullable=True)
    last_sync_timestamp = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
            'created_at': self.created_at.isoformat()
        }
