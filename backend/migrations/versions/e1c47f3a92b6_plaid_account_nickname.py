"""plaid account nickname (user custom label)

Revision ID: e1c47f3a92b6
Revises: d8b2e91c4a55
Create Date: 2026-07-18

User-set display label for a linked account, stored separately from the raw
Plaid-provided name so a rename never touches the synced data. Null = use the
Plaid name.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e1c47f3a92b6'
down_revision = 'd8b2e91c4a55'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('plaid_accounts', sa.Column('nickname', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('plaid_accounts', 'nickname')
