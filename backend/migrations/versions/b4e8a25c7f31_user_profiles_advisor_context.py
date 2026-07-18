"""user profiles (advisor context)

Revision ID: b4e8a25c7f31
Revises: 1f8d70109e12
Create Date: 2026-07-16

Separate table for sensitive personal/financial context used by the AI
advisor — deliberately not columns on the auth `user` table.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b4e8a25c7f31'
down_revision = '1f8d70109e12'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('employment_status', sa.String(length=20), nullable=True),
        sa.Column('annual_income', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('marital_status', sa.String(length=10), nullable=True),
        sa.Column('dependents', sa.SmallInteger(), nullable=True),
        sa.Column('housing_status', sa.String(length=10), nullable=True),
        sa.Column('birth_year', sa.SmallInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade():
    op.drop_table('user_profiles')
