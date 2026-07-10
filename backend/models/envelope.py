from datetime import datetime
from models.user import db

# Allowed values for EnvelopeAllocation.source_type
ALLOCATION_SOURCE_TYPES = ('paycheck_split', 'manual', 'withdrawal', 'correction')

# Allowed values for AllocationRule.allocation_type
ALLOCATION_RULE_TYPES = ('fixed_amount', 'percentage', 'remainder')


class EnvelopeAllocation(db.Model):
    """Ledger of every dollar moved into (+) or out of (-) a goal's envelope.
    Balances are derived by summing rows, never stored as a counter alone."""
    __tablename__ = 'envelope_allocations'

    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer,
                        db.ForeignKey('financial_goals.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # positive = funded, negative = withdrawn
    source_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    source_type = db.Column(db.String(20), nullable=False, default='manual')
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    goal = db.relationship('FinancialGoal',
                           backref=db.backref('allocations', lazy=True,
                                              cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'goal_id': self.goal_id,
            'amount': float(self.amount),
            'source_transaction_id': self.source_transaction_id,
            'source_type': self.source_type,
            'note': self.note,
            'created_at': self.created_at.isoformat()
        }

    def __repr__(self):
        return f'<EnvelopeAllocation goal={self.goal_id} ${self.amount} ({self.source_type})>'


class AllocationRule(db.Model):
    """Priority-ordered waterfall for splitting income across goals.
    Used in Phase 2 to pre-fill the paycheck allocation prompt."""
    __tablename__ = 'allocation_rules'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    goal_id = db.Column(db.Integer,
                        db.ForeignKey('financial_goals.id', ondelete='CASCADE'),
                        nullable=False)
    priority_order = db.Column(db.Integer, nullable=False)
    allocation_type = db.Column(db.String(20), nullable=False)  # fixed_amount | percentage | remainder
    fixed_amount = db.Column(db.Numeric(12, 2), nullable=True)
    percentage = db.Column(db.Numeric(5, 2), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    goal = db.relationship('FinancialGoal',
                           backref=db.backref('allocation_rule', uselist=False,
                                              cascade='all, delete-orphan'))

    # One rule per goal per user
    __table_args__ = (
        db.UniqueConstraint('user_id', 'goal_id', name='unique_user_goal_rule'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'goal_id': self.goal_id,
            'goal_name': self.goal.name if self.goal else None,
            'priority_order': self.priority_order,
            'allocation_type': self.allocation_type,
            'fixed_amount': float(self.fixed_amount) if self.fixed_amount is not None else None,
            'percentage': float(self.percentage) if self.percentage is not None else None,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f'<AllocationRule goal={self.goal_id} #{self.priority_order} {self.allocation_type}>'
