from datetime import datetime
from models.user import db

INCOME_EVENT_STATUSES = ('pending', 'confirmed', 'dismissed')


class IncomeEvent(db.Model):
    """A detected likely-income deposit awaiting an allocation decision.
    One event per transaction; status tracks whether the user split it,
    dismissed it, or hasn't responded yet."""
    __tablename__ = 'income_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'),
                               unique=True, nullable=False)
    plaid_account_id = db.Column(db.Integer, db.ForeignKey('plaid_accounts.id'), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    transaction = db.relationship('Transaction', backref=db.backref('income_event', uselist=False))
    account = db.relationship('PlaidAccount', backref=db.backref('income_events', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'plaid_account_id': self.plaid_account_id,
            'account_name': self.account.name if self.account else None,
            'amount': float(self.amount),
            'status': self.status,
            'detected_at': self.detected_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'description': self.transaction.description if self.transaction else None,
            'transaction_date': self.transaction.transaction_date.isoformat() if self.transaction else None
        }

    def __repr__(self):
        return f'<IncomeEvent ${self.amount} ({self.status})>'
