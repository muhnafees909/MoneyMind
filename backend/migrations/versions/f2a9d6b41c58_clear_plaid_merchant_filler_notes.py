"""clear plaid merchant-filler notes

Revision ID: f2a9d6b41c58
Revises: e1c47f3a92b6
Create Date: 2026-07-23

Notes are now a user-authored field usable on any transaction. Older synced
rows had transaction_notes auto-populated with "Merchant: <name>", which would
make every Plaid row look like it carries a user note. Clear that filler so the
has-a-note indicator is meaningful. Safe: Plaid notes were never user-editable
before this change, so nothing here is user data. Manual rows are untouched.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f2a9d6b41c58'
down_revision = 'e1c47f3a92b6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE transactions SET transaction_notes = '' "
        "WHERE source = 'plaid' AND transaction_notes LIKE 'Merchant: %'"
    )


def downgrade():
    # One-way data cleanup; the filler is regenerable from merchant_name if ever
    # needed, so there is nothing meaningful to restore.
    pass
