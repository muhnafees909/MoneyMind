"""plaid item reauth state

Add needs_reauth + last_error_code to plaid_items so a Plaid item-level error
(e.g. ITEM_LOGIN_REQUIRED) can be recorded and surfaced to the user as a
reconnect prompt, then cleared on the next successful sync.

Revision ID: f3a91c26d0b8
Revises: b7c2e04a91f8
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a91c26d0b8'
down_revision = 'b7c2e04a91f8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'plaid_items',
        sa.Column('needs_reauth', sa.Boolean(), nullable=False,
                  server_default=sa.false())
    )
    op.add_column(
        'plaid_items',
        sa.Column('last_error_code', sa.String(length=60), nullable=True)
    )
    # Drop the server_default now that existing rows are backfilled to False —
    # the model manages the value going forward.
    op.alter_column('plaid_items', 'needs_reauth', server_default=None)


def downgrade():
    op.drop_column('plaid_items', 'last_error_code')
    op.drop_column('plaid_items', 'needs_reauth')
