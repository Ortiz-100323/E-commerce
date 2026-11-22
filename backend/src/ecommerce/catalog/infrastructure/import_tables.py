from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from ecommerce.shared_kernel.domain.actor import MAX_ACTOR_LENGTH
from ecommerce.shared_kernel.infrastructure.database import metadata

OUTCOMES = "('create', 'update', 'unchanged', 'needs_review', 'rejected', 'superseded', 'blank')"

import_batches = Table(
    "import_batches",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("file_name", String(255), nullable=False),
    Column("file_sha256", String(64), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("uploaded_by", String(MAX_ACTOR_LENGTH), nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("file_warnings", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("result", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint(
        "status IN ('PENDING_REVIEW', 'COMMITTED', 'DISCARDED', 'EXPIRED')",
        name="ck_import_batches_known_status",
    ),
    Index("ix_import_batches_sha256_status", "file_sha256", "status"),
)

import_batch_rows = Table(
    "import_batch_rows",
    metadata,
    Column(
        "batch_id",
        Uuid,
        ForeignKey("import_batches.id", name="fk_import_batch_rows_batch"),
        nullable=False,
    ),
    Column("line", Integer, nullable=False),
    Column("raw", Text, nullable=False),
    Column("raw_values", JSONB, nullable=False),
    Column("current_values", JSONB, nullable=False),
    Column("original_outcome", String(16), nullable=False),
    Column("outcome", String(16), nullable=False),
    Column("issues", JSONB, nullable=False),
    Column("product", JSONB, nullable=False),
    Column("changes", JSONB, nullable=False),
    Column("target_product_id", Uuid, nullable=True),
    Column("target_version", Integer, nullable=True),
    Column("needs_confirmation", Boolean, nullable=False),
    Column("superseded_by", Integer, nullable=True),
    Column("decision", String(16), nullable=True),
    Column("confirmed", JSONB, nullable=False),
    Column("history", JSONB, nullable=False),
    PrimaryKeyConstraint("batch_id", "line", name="pk_import_batch_rows"),
    CheckConstraint(f"outcome IN {OUTCOMES}", name="ck_import_batch_rows_known_outcome"),
    CheckConstraint(
        f"original_outcome IN {OUTCOMES}", name="ck_import_batch_rows_known_original_outcome"
    ),
    CheckConstraint(
        "decision IS NULL OR decision IN ('confirmed', 'skipped')",
        name="ck_import_batch_rows_known_decision",
    ),
)
