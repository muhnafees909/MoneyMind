"""advisor usage log and abuse flags

Revision ID: c5f1a02d8e47
Revises: b4e8a25c7f31
Create Date: 2026-07-17

Request log for AI advisor rate limiting (per-minute burst + daily cost
cap), the in-UI usage indicator, and abuse-pattern review flags.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c5f1a02d8e47'
down_revision = 'b4e8a25c7f31'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'advisor_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('message_hash', sa.String(length=64), nullable=False),
        sa.Column('message_chars', sa.Integer(), nullable=False),
        sa.Column('was_limited', sa.Boolean(), nullable=False),
        sa.Column('limit_kind', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_advisor_usage_user_id', 'advisor_usage', ['user_id'])
    op.create_index('ix_advisor_usage_created_at', 'advisor_usage', ['created_at'])

    op.create_table(
        'advisor_abuse_flags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=40), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_advisor_abuse_flags_user_id', 'advisor_abuse_flags', ['user_id'])


def downgrade():
    op.drop_index('ix_advisor_abuse_flags_user_id', table_name='advisor_abuse_flags')
    op.drop_table('advisor_abuse_flags')
    op.drop_index('ix_advisor_usage_created_at', table_name='advisor_usage')
    op.drop_index('ix_advisor_usage_user_id', table_name='advisor_usage')
    op.drop_table('advisor_usage')
