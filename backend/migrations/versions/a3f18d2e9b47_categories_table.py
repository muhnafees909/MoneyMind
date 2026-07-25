"""categories table (system defaults + user custom categories)

Revision ID: a3f18d2e9b47
Revises: f2a9d6b41c58
Create Date: 2026-07-23

Adds a categories table so users can create custom categories alongside the
system defaults. This is PURELY ADDITIVE:
  - transactions/budgets/recurring.category are already free-text VARCHAR
    columns (never a DB enum), so nothing about existing rows changes.
  - The 16 default category keys already stored on existing rows are seeded
    here as system rows (user_id NULL), so they resolve to names/colors/icons
    exactly as before.
  - A catch-all 'UNCATEGORIZED' system category is seeded for delete-reassign.
No existing data is rewritten or migrated.
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'a3f18d2e9b47'
down_revision = 'f2a9d6b41c58'
branch_labels = None
depends_on = None


# Kept inline (not imported from the model) so the migration is self-contained
# and stable even if the model's default list changes later.
_SEED = [
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
    ('UNCATEGORIZED', 'Uncategorized', '#86817a', 'circle-dashed'),
]


def upgrade():
    categories = op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('value', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=40), nullable=False),
        sa.Column('color', sa.String(length=9), nullable=False),
        sa.Column('icon', sa.String(length=40), nullable=False, server_default='tag'),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'value', name='uq_category_user_value'),
    )
    op.create_index('ix_categories_user_id', 'categories', ['user_id'])
    op.create_index('ix_categories_value', 'categories', ['value'])

    # Seed system defaults (user_id NULL)
    now = datetime.utcnow()
    op.bulk_insert(categories, [
        {'user_id': None, 'value': v, 'name': n, 'color': c, 'icon': i,
         'archived': False, 'created_at': now}
        for (v, n, c, i) in _SEED
    ])


def downgrade():
    op.drop_index('ix_categories_value', table_name='categories')
    op.drop_index('ix_categories_user_id', table_name='categories')
    op.drop_table('categories')
