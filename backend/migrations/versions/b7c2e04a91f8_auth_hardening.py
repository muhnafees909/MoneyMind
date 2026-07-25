"""auth hardening: email verification, MFA, login lockouts

Revision ID: b7c2e04a91f8
Revises: a3f18d2e9b47
Create Date: 2026-07-24

Adds:
  - user.email_verified / verification_token_hash / verification_sent_at
  - user.mfa_enabled / mfa_secret
  - mfa_backup_codes (hashed one-time recovery codes)
  - login_attempts (failed-login audit log)
  - login_lockouts (email+IP escalating cooldown state)

Additive and backfill-safe: existing users get email_verified=False and
mfa_enabled=False. (A follow-up can mark pre-existing accounts verified if you
don't want to re-verify them — see note in routes/auth.py.)
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7c2e04a91f8'
down_revision = 'a3f18d2e9b47'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('email_verified', sa.Boolean(), nullable=False,
                                    server_default=sa.false()))
    op.add_column('user', sa.Column('verification_token_hash', sa.String(length=64), nullable=True))
    op.add_column('user', sa.Column('verification_sent_at', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('mfa_enabled', sa.Boolean(), nullable=False,
                                    server_default=sa.false()))
    op.add_column('user', sa.Column('mfa_secret', sa.String(length=255), nullable=True))
    op.create_index('ix_user_verification_token_hash', 'user', ['verification_token_hash'])

    op.create_table(
        'mfa_backup_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mfa_backup_codes_user_id', 'mfa_backup_codes', ['user_id'])

    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('successful', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_login_attempts_email', 'login_attempts', ['email'])
    op.create_index('ix_login_attempts_ip', 'login_attempts', ['ip'])
    op.create_index('ix_login_attempts_created_at', 'login_attempts', ['created_at'])

    op.create_table(
        'login_lockouts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=False),
        sa.Column('fail_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lock_level', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'ip', name='uq_login_lockout_email_ip'),
    )
    op.create_index('ix_login_lockout_email_ip', 'login_lockouts', ['email', 'ip'])


def downgrade():
    op.drop_table('login_lockouts')
    op.drop_index('ix_login_attempts_created_at', table_name='login_attempts')
    op.drop_index('ix_login_attempts_ip', table_name='login_attempts')
    op.drop_index('ix_login_attempts_email', table_name='login_attempts')
    op.drop_table('login_attempts')
    op.drop_index('ix_mfa_backup_codes_user_id', table_name='mfa_backup_codes')
    op.drop_table('mfa_backup_codes')
    op.drop_index('ix_user_verification_token_hash', table_name='user')
    op.drop_column('user', 'mfa_secret')
    op.drop_column('user', 'mfa_enabled')
    op.drop_column('user', 'verification_sent_at')
    op.drop_column('user', 'verification_token_hash')
    op.drop_column('user', 'email_verified')
