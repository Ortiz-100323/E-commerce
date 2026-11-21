import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_searches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("query", sa.String(100), nullable=False),
        sa.Column("location_name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("latitude", sa.Double(), nullable=False),
        sa.Column("longitude", sa.Double(), nullable=False),
        sa.Column("temperature_c", sa.Double(), nullable=False),
        sa.Column("wind_speed_kmh", sa.Double(), nullable=False),
        sa.Column("weather_code", sa.Integer(), nullable=False),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_weather_searches_searched_at", "weather_searches", ["searched_at"])


def downgrade() -> None:
    op.drop_index("ix_weather_searches_searched_at", table_name="weather_searches")
    op.drop_table("weather_searches")
