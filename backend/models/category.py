from datetime import datetime
from models.user import db


# The 16 system default categories (mirror the Plaid primaries). user_id is NULL
# for these — they belong to everyone and cannot be edited or deleted.
# (value, display name, color, lucide icon name)
DEFAULT_CATEGORIES = [
    ('INCOME', 'Income', '#27b9de', 'banknote'),
    ('TRANSFER_IN', 'Transfer In', '#6c9de6', 'arrow-down-left'),
    ('TRANSFER_OUT', 'Transfer Out', '#b189e0', 'arrow-up-right'),
    ('LOAN_PAYMENTS', 'Loan Payments', '#8f93ea', 'landmark'),
    ('BANK_FEES', 'Bank Fees', '#8f93ea', 'receipt'),
    ('ENTERTAINMENT', 'Entertainment', '#b189e0', 'clapperboard'),
    ('FOOD_AND_DRINK', 'Food & Drink', '#e27c4e', 'utensils'),
    ('GENERAL_MERCHANDISE', 'Shopping', '#e07b9f', 'shopping-bag'),
    ('HOME_IMPROVEMENT', 'Home Improvement', '#a9bf49', 'hammer'),
    ('MEDICAL', 'Healthcare', '#a9bf49', 'heart-pulse'),
    ('PERSONAL_CARE', 'Personal Care', '#e07b9f', 'sparkles'),
    ('GENERAL_SERVICES', 'Services', '#e27c4e', 'wrench'),
    ('GOVERNMENT_AND_NON_PROFIT', 'Government & Non-Profit', '#dba43e', 'building-2'),
    ('TRANSPORTATION', 'Transportation', '#dba43e', 'car'),
    ('TRAVEL', 'Travel', '#27b9de', 'plane'),
    ('RENT_AND_UTILITIES', 'Rent & Utilities', '#6c9de6', 'house'),
]

# The catch-all system category that deleted custom categories reassign into.
UNCATEGORIZED_VALUE = 'UNCATEGORIZED'
UNCATEGORIZED = (UNCATEGORIZED_VALUE, 'Uncategorized', '#86817a', 'circle-dashed')


class Category(db.Model):
    """A spending category. System categories (user_id NULL) are the shared
    defaults everyone sees; user categories are custom ones a single user
    created. The `value` string is what gets stored in
    transactions/budgets/recurring.category — existing rows already hold these
    strings, so seeding the defaults here is purely additive."""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    # NULL = system default (global); set = a user's custom category
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    # The stable key persisted on transactions/budgets/recurring
    value = db.Column(db.String(60), nullable=False, index=True)
    name = db.Column(db.String(40), nullable=False)          # display name
    color = db.Column(db.String(9), nullable=False)          # hex
    icon = db.Column(db.String(40), nullable=False, default='tag')  # lucide icon name
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        # A value is unique within a scope (per user, and once globally for system)
        db.UniqueConstraint('user_id', 'value', name='uq_category_user_value'),
    )

    @property
    def is_system(self):
        return self.user_id is None

    def to_dict(self):
        return {
            'id': self.id,
            'value': self.value,
            'display_name': self.name,
            'color': self.color,
            'icon': self.icon,
            'is_system': self.is_system,
            'is_custom': not self.is_system,
            'archived': self.archived,
        }

    def __repr__(self):
        scope = 'system' if self.is_system else f'user {self.user_id}'
        return f'<Category {self.value} ({scope})>'
