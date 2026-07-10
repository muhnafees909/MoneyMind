from datetime import datetime
from models.user import db


class PlaidAccount(db.Model):
    """A single bank account under a PlaidItem (an item can hold checking + savings etc.).
    Stores the latest known balance so envelopes can reconcile against it."""
    __tablename__ = 'plaid_accounts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plaid_item_id = db.Column(db.Integer, db.ForeignKey('plaid_items.id'), nullable=False)

    plaid_account_id = db.Column(db.String(255), unique=True, nullable=False)  # Plaid's account_id
    name = db.Column(db.String(255), nullable=False)
    official_name = db.Column(db.String(255), nullable=True)
    account_type = db.Column(db.String(50), nullable=True)      # depository, credit, ...
    account_subtype = db.Column(db.String(50), nullable=True)   # checking, savings, ...
    mask = db.Column(db.String(10), nullable=True)              # last 4 digits

    current_balance = db.Column(db.Numeric(12, 2), nullable=True)
    available_balance = db.Column(db.Numeric(12, 2), nullable=True)
    iso_currency_code = db.Column(db.String(10), nullable=True)
    balance_updated_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plaid_item = db.relationship('PlaidItem', backref=db.backref('accounts', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'plaid_item_id': self.plaid_item_id,
            'plaid_account_id': self.plaid_account_id,
            'name': self.name,
            'official_name': self.official_name,
            'account_type': self.account_type,
            'account_subtype': self.account_subtype,
            'mask': self.mask,
            'current_balance': float(self.current_balance) if self.current_balance is not None else None,
            'available_balance': float(self.available_balance) if self.available_balance is not None else None,
            'iso_currency_code': self.iso_currency_code,
            'balance_updated_at': self.balance_updated_at.isoformat() if self.balance_updated_at else None,
            'institution_name': self.plaid_item.institution_name if self.plaid_item else None
        }

    def __repr__(self):
        return f'<PlaidAccount {self.name} (*{self.mask}): ${self.current_balance}>'
