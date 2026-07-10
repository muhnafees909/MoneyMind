from datetime import datetime
from decimal import Decimal
from models.user import db

RECURRING_CADENCES = ('weekly', 'biweekly', 'monthly', 'annual')
RECURRING_STATUSES = ('active', 'dismissed', 'cancelled_by_user')

# Latest charge must exceed the average of the prior few by this much to flag price creep
PRICE_CREEP_THRESHOLD = Decimal('0.10')


class RecurringExpense(db.Model):
    """A detected recurring charge (subscription, bill). Created unconfirmed by
    the detection job; the user confirms or dismisses it in the review queue."""
    __tablename__ = 'recurring_expenses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    merchant_name = db.Column(db.String(255), nullable=False)   # display name (raw description)
    merchant_key = db.Column(db.String(255), nullable=False)    # normalized key used for matching
    category = db.Column(db.String(50), nullable=True)          # links to Budget tab by category string
    expected_amount = db.Column(db.Numeric(12, 2), nullable=False)
    cadence = db.Column(db.String(20), nullable=False)          # weekly | biweekly | monthly | annual
    next_expected_date = db.Column(db.Date, nullable=True)

    status = db.Column(db.String(20), nullable=False, default='active')
    confirmed_by_user = db.Column(db.Boolean, default=False)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    occurrences = db.relationship('RecurringExpenseOccurrence',
                                  backref='recurring_expense',
                                  lazy=True,
                                  cascade='all, delete-orphan',
                                  order_by='RecurringExpenseOccurrence.occurred_at')

    @property
    def monthly_equivalent(self):
        """Normalized monthly cost, for the Budget tab subtotal."""
        amount = Decimal(self.expected_amount)
        factor = {
            'weekly': Decimal('52') / 12,
            'biweekly': Decimal('26') / 12,
            'monthly': Decimal('1'),
            'annual': Decimal('1') / 12
        }.get(self.cadence, Decimal('1'))
        return (amount * factor).quantize(Decimal('0.01'))

    @property
    def price_creep(self):
        """Compare the latest charge to the average of the previous (up to 3)
        occurrences. Returns dict when it jumped > threshold, else None."""
        if len(self.occurrences) < 2:
            return None
        latest = self.occurrences[-1]
        priors = self.occurrences[-4:-1]
        prior_avg = sum(Decimal(o.amount) for o in priors) / len(priors)
        if prior_avg <= 0:
            return None
        increase = (Decimal(latest.amount) - prior_avg) / prior_avg
        if increase > PRICE_CREEP_THRESHOLD:
            return {
                'previous_average': float(prior_avg.quantize(Decimal('0.01'))),
                'latest_amount': float(latest.amount),
                'increase_pct': float((increase * 100).quantize(Decimal('0.1')))
            }
        return None

    def to_dict(self, include_occurrences=False):
        data = {
            'id': self.id,
            'merchant_name': self.merchant_name,
            'category': self.category,
            'expected_amount': float(self.expected_amount),
            'monthly_equivalent': float(self.monthly_equivalent),
            'cadence': self.cadence,
            'next_expected_date': self.next_expected_date.isoformat() if self.next_expected_date else None,
            'status': self.status,
            'confirmed_by_user': self.confirmed_by_user,
            'detected_at': self.detected_at.isoformat(),
            'occurrence_count': len(self.occurrences),
            'last_amount': float(self.occurrences[-1].amount) if self.occurrences else None,
            'last_occurred_at': self.occurrences[-1].occurred_at.isoformat() if self.occurrences else None,
            'price_creep': self.price_creep
        }
        if include_occurrences:
            data['occurrences'] = [o.to_dict() for o in self.occurrences]
        return data

    def __repr__(self):
        return f'<RecurringExpense {self.merchant_name} ${self.expected_amount}/{self.cadence}>'


class RecurringExpenseOccurrence(db.Model):
    """One actual transaction belonging to a recurring series — the audit trail
    that lets us compute drift and confidence over time."""
    __tablename__ = 'recurring_expense_occurrences'

    id = db.Column(db.Integer, primary_key=True)
    recurring_expense_id = db.Column(db.Integer,
                                     db.ForeignKey('recurring_expenses.id', ondelete='CASCADE'),
                                     nullable=False, index=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'),
                               unique=True, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    occurred_at = db.Column(db.Date, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'amount': float(self.amount),
            'occurred_at': self.occurred_at.isoformat()
        }
