from datetime import datetime
from decimal import Decimal
from models.user import db

class Transaction(db.Model):

    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    transaction_date = db.Column(db.DateTime, nullable=False)
    transaction_notes = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(20), default='manual')  # 'manual' or 'plaid'
    plaid_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
    # Which bank account this landed on (Plaid-synced transactions only)
    plaid_account_id = db.Column(db.Integer, db.ForeignKey('plaid_accounts.id'), nullable=True)
    # Plaid's cleaned merchant name (e.g. "Netflix") — distinct from the raw description
    merchant_name = db.Column(db.String(255), nullable=True)
    # Plaid's stable merchant entity id — the most reliable recurring-match key when present
    merchant_entity_id = db.Column(db.String(255), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount),
            'description': self.description,
            'category': self.category,
            'transaction_type': self.transaction_type,
            'transaction_date': self.transaction_date.isoformat(),
            'transaction_notes': self.transaction_notes,
            'source': self.source,
            'plaid_transaction_id': self.plaid_transaction_id,
            'plaid_account_id': self.plaid_account_id,
            'merchant_name': self.merchant_name,
            'merchant_entity_id': self.merchant_entity_id,
            'created_at': self.created_at.isoformat()
        }

    def __repr__(self):
        return f'<Transaction {self.id}: ${self.amount} - {self.description} - {self.created_at}>'
