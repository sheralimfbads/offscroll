"""Persist source lanes and template summaries without YouTube-derived scores."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: str = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "digests",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("window_kind", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("config_snapshot", JSONB(), nullable=False),
        sa.UniqueConstraint("week_start", "week_end", "window_kind", name="uq_digest_window"),
        sa.CheckConstraint("window_kind IN ('rolling', 'iso_week')", name="ck_digest_window_kind"),
        sa.CheckConstraint("week_end = week_start + 7", name="ck_digest_week"),
        schema="core",
    )
    op.create_table(
        "item_summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("core.items.id", ondelete="SET NULL")),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_estimate", sa.Numeric(14, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('hackernews', 'wikipedia')", name="ck_summary_source"),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND cost_estimate >= 0",
            name="ck_summary_usage",
        ),
        schema="core",
    )
    op.create_table(
        "digest_items",
        sa.Column(
            "digest_id",
            sa.BigInteger(),
            sa.ForeignKey("core.digests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("lane", sa.Text(), primary_key=True),
        sa.Column("lane_rank", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("core.items.id", ondelete="SET NULL")),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("score_breakdown", JSONB(), nullable=False),
        sa.Column("cluster", JSONB(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("summary_id", sa.BigInteger(), sa.ForeignKey("core.item_summaries.id")),
        sa.UniqueConstraint("digest_id", "item_id", name="uq_digest_item"),
        sa.CheckConstraint(
            "(lane = 'hackernews' AND lane_rank BETWEEN 1 AND 6) OR "
            "(lane = 'wikipedia' AND lane_rank BETWEEN 1 AND 5) OR "
            "(lane = 'youtube' AND lane_rank BETWEEN 1 AND 4)",
            name="ck_digest_lane",
        ),
        sa.CheckConstraint(
            "((lane = 'youtube' AND final_score IS NULL "
            "AND score_breakdown = '{}'::jsonb AND cluster = '[]'::jsonb "
            "AND summary_id IS NULL "
            "AND content ? 'video_id' AND content ? 'url' "
            "AND content->>'video_id' ~ '^[A-Za-z0-9_-]{11}$' "
            "AND content->>'url' = 'https://www.youtube.com/watch?v=' || (content->>'video_id') "
            "AND content = jsonb_build_object('video_id', content->>'video_id', "
            "'url', content->>'url')) "
            "OR (lane IN ('hackernews', 'wikipedia') "
            "AND final_score BETWEEN 0 AND 1.3)) IS TRUE",
            name="ck_digest_youtube_isolation",
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("digest_items", schema="core")
    op.drop_table("item_summaries", schema="core")
    op.drop_table("digests", schema="core")
