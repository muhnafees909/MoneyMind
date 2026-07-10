from datetime import datetime
from models.user import db

class FinancialGoal(db.Model):
    __tablename__ = 'financial_goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Goal details
    name = db.Column(db.String(100), nullable=False)  # "Emergency Fund", "Vacation"
    description = db.Column(db.Text, nullable=True)
    target_amount = db.Column(db.Numeric(10, 2), nullable=False)
    current_amount = db.Column(db.Numeric(10, 2), default=0)
    target_date = db.Column(db.Date, nullable=True)  # Optional deadline
    
    # Status
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Envelope mode: set linked_account_id to treat this goal as a virtual
    # sub-allocation ("envelope") of a real Plaid-linked account
    linked_account_id = db.Column(db.Integer, db.ForeignKey('plaid_accounts.id'), nullable=True)
    priority_order = db.Column(db.Integer, nullable=True)  # rank in allocation waterfall (1 = first funded)

    linked_account = db.relationship('PlaidAccount',
                                     backref=db.backref('envelope_goals', lazy=True))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'target_amount': float(self.target_amount),
            'current_amount': float(self.current_amount),
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'is_completed': self.is_completed,
            'completed_at': self.completed_at.date().isoformat() if self.completed_at else None,  # Just date, not datetime
            'progress_percentage': self.progress_percentage,
            'remaining_amount': float(self.target_amount - self.current_amount),
            'linked_account_id': self.linked_account_id,
            'linked_account_name': self.linked_account.name if self.linked_account else None,
            'priority_order': self.priority_order,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.target_amount == 0:
            return 0
        percentage = (self.current_amount / self.target_amount) * 100
        return min(percentage, 100)  # Cap at 100%
    
    def __repr__(self):
        return f'<FinancialGoal {self.name}: ${self.current_amount}/${self.target_amount}>'