import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('ADMIN', 'BUYER')", name="ck_accounts_known_role"),
        sa.CheckConstraint("email = lower(email)", name="ck_accounts_email_lower_case"),
    )
    op.create_index("ux_accounts_email", "accounts", ["email"], unique=True)
    op.create_table(
        "account_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", name="fk_account_sessions_account", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ux_account_sessions_token_hash", "account_sessions", ["token_hash"], unique=True
    )
    op.create_index("ix_account_sessions_account", "account_sessions", ["account_id"])


def downgrade() -> None:
    op.drop_table("account_sessions")
    op.drop_table("accounts")
