"""transaction category_source (manual override tracking)

Revision ID: d8b2e91c4a55
Revises: c5f1a02d8e47
Create Date: 2026-07-17

Tracks whether a transaction's category was auto-assigned (Plaid/detection)
or set by the user, so bank re-syncs never silently overwrite a manual
correction. Existing rows are all 'auto' — nothing was user-set until now.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd8b2e91c4a55'
down_revision = 'c5f1a02d8e47'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'transactions',
        sa.Column('category_source', sa.String(length=10), nullable=False,
                  server_default='auto')
    )


def downgrade():
    op.drop_column('transactions', 'category_source')
