from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Uuid,
    true,
)

from ecommerce.identity.domain.account import MAX_ACCOUNT_NAME_LENGTH, MAX_EMAIL_LENGTH
from ecommerce.shared_kernel.infrastructure.database import metadata

accounts = Table(
    "accounts",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(MAX_EMAIL_LENGTH), nullable=False),
    Column("name", String(MAX_ACCOUNT_NAME_LENGTH), nullable=False),
    Column("role", String(16), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("active", Boolean, nullable=False, server_default=true()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("role IN ('ADMIN', 'BUYER')", name="ck_accounts_known_role"),
    CheckConstraint("email = lower(email)", name="ck_accounts_email_lower_case"),
    Index("ux_accounts_email", "email", unique=True),
)

account_sessions = Table(
    "account_sessions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "account_id",
        Uuid,
        ForeignKey("accounts.id", name="fk_account_sessions_account", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("token_hash", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Index("ux_account_sessions_token_hash", "token_hash", unique=True),
    Index("ix_account_sessions_account", "account_id"),
)
