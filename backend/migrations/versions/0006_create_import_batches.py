import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

OUTCOMES = "('create', 'update', 'unchanged', 'needs_review', 'rejected', 'superseded', 'blank')"


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("uploaded_by", sa.String(100), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "file_warnings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_REVIEW', 'COMMITTED', 'DISCARDED', 'EXPIRED')",
            name="ck_import_batches_known_status",
        ),
    )
    op.create_index("ix_import_batches_sha256_status", "import_batches", ["file_sha256", "status"])
    op.create_table(
        "import_batch_rows",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("raw", sa.Text(), nullable=False),
        sa.Column("raw_values", postgresql.JSONB(), nullable=False),
        sa.Column("current_values", postgresql.JSONB(), nullable=False),
        sa.Column("original_outcome", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("issues", postgresql.JSONB(), nullable=False),
        sa.Column("product", postgresql.JSONB(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("target_product_id", sa.Uuid(), nullable=True),
        sa.Column("target_version", sa.Integer(), nullable=True),
        sa.Column("needs_confirmation", sa.Boolean(), nullable=False),
        sa.Column("superseded_by", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("confirmed", postgresql.JSONB(), nullable=False),
        sa.Column("history", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("batch_id", "line", name="pk_import_batch_rows"),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["import_batches.id"], name="fk_import_batch_rows_batch"
        ),
        sa.CheckConstraint(f"outcome IN {OUTCOMES}", name="ck_import_batch_rows_known_outcome"),
        sa.CheckConstraint(
            f"original_outcome IN {OUTCOMES}",
            name="ck_import_batch_rows_known_original_outcome",
        ),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('confirmed', 'skipped')",
            name="ck_import_batch_rows_known_decision",
        ),
    )


def downgrade() -> None:
    op.drop_table("import_batch_rows")
    op.drop_index("ix_import_batches_sha256_status", table_name="import_batches")
    op.drop_table("import_batches")
