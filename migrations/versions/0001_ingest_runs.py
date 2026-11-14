"""Create data schemas and the ingestion run log."""

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema("raw"))
    op.execute(sa.schema.CreateSchema("core"))
    op.execute(sa.schema.CreateSchema("marts"))
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("items_fetched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        schema="raw",
    )


def downgrade() -> None:
    op.drop_table("ingest_runs", schema="raw")
    # No CASCADE: refuse to remove schemas containing unrelated objects.
    op.execute(sa.schema.DropSchema("marts"))
    op.execute(sa.schema.DropSchema("core"))
    op.execute(sa.schema.DropSchema("raw"))
