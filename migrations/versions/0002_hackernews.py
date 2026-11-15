"""Land raw API responses and store normalized items and metric snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "ingest_runs",
        sa.Column("items_rejected", sa.Integer(), nullable=False, server_default="0"),
        schema="raw",
    )
    op.create_check_constraint(
        "ck_runs_rejected", "ingest_runs", "items_rejected >= 0", schema="raw"
    )
    op.create_check_constraint(
        "ck_runs_status",
        "ingest_runs",
        "status IN ('running', 'succeeded', 'failed')",
        schema="raw",
    )
    op.create_table(
        "api_responses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("raw.ingest_runs.id"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.CheckConstraint("http_status BETWEEN 100 AND 599", name="ck_response_status"),
        schema="raw",
    )
    op.create_table(
        "sources",
        sa.Column("source", sa.Text(), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("raw_retention_days", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("raw_retention_days > 0", name="ck_source_retention"),
        schema="core",
    )
    op.execute(
        sa.text(
            "INSERT INTO core.sources VALUES "
            "('hackernews', 'Hacker News', 90, "
            "'Project policy: purge raw API responses after 90 days.')"
        )
    )
    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source", sa.Text(), sa.ForeignKey("core.sources.source"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("discussion_url", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("source", "external_id", name="uq_item_source_external"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_item_title"),
        sa.CheckConstraint("length(external_id) > 0", name="ck_item_external"),
        sa.CheckConstraint("last_seen_at >= first_seen_at", name="ck_item_seen_times"),
        schema="core",
    )
    op.create_index(
        "ix_items_source_published",
        "items",
        ["source", sa.text("published_at DESC")],
        schema="core",
    )
    op.create_table(
        "item_snapshots",
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("core.items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("raw.ingest_runs.id"), primary_key=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.BigInteger(), nullable=True),
        sa.Column("comments", sa.BigInteger(), nullable=True),
        sa.Column("views", sa.BigInteger(), nullable=True),
        sa.Column("likes", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "score >= 0 AND comments >= 0 AND views >= 0 AND likes >= 0", name="ck_snapshot_metrics"
        ),
        schema="core",
    )
    op.create_index(
        "ix_snapshots_item_captured", "item_snapshots", ["item_id", "captured_at"], schema="core"
    )
    op.execute(
        sa.text("""
        CREATE VIEW marts.latest_item_metrics AS
        SELECT DISTINCT ON (i.id) i.*, s.run_id AS snapshot_run_id,
               s.captured_at, s.score, s.comments, s.views, s.likes
        FROM core.items AS i JOIN core.item_snapshots AS s ON s.item_id = i.id
        ORDER BY i.id, s.captured_at DESC, s.run_id DESC
    """)
    )


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW marts.latest_item_metrics"))
    op.drop_table("item_snapshots", schema="core")
    op.drop_table("items", schema="core")
    op.drop_table("sources", schema="core")
    op.drop_table("api_responses", schema="raw")
    op.drop_constraint("ck_runs_status", "ingest_runs", schema="raw")
    op.drop_constraint("ck_runs_rejected", "ingest_runs", schema="raw")
    op.drop_column("ingest_runs", "items_rejected", schema="raw")
