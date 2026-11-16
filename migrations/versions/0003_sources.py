"""Add curated YouTube channel cache and durable daily quota accounting."""

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        INSERT INTO core.sources (source, display_name, raw_retention_days, notes) VALUES
        ('wikipedia', 'Wikipedia', 90, 'Project policy: raw pageviews retained for 90 days.'),
        ('youtube', 'YouTube', 30, 'Delete or refresh raw and core API data within 30 days.')
    """)
    )
    op.create_table(
        "youtube_channels",
        sa.Column("channel_id", sa.Text(), primary_key=True),
        sa.Column("handle", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("uploads_playlist_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Cache age is necessary to enforce the requested 30-day retention rule.
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        schema="core",
    )
    op.create_table(
        "api_quota_usage",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("source", sa.Text(), primary_key=True),
        sa.Column("units", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("units >= 0", name="ck_quota_units"),
        schema="raw",
    )


def downgrade() -> None:
    op.drop_table("api_quota_usage", schema="raw")
    op.drop_table("youtube_channels", schema="core")
    # The shared M2 tables stay intact; only M3 source data is removed.
    op.execute(sa.text("DELETE FROM core.items WHERE source IN ('wikipedia', 'youtube')"))
    op.execute(sa.text("DELETE FROM raw.api_responses WHERE source IN ('wikipedia', 'youtube')"))
    op.execute(sa.text("DELETE FROM raw.ingest_runs WHERE source IN ('wikipedia', 'youtube')"))
    op.execute(sa.text("DELETE FROM core.sources WHERE source IN ('wikipedia', 'youtube')"))
