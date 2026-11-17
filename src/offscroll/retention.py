"""Purge expired raw data and YouTube-derived core data, without network access."""

from sqlalchemy import Engine, text


def purge_expired(engine: Engine) -> dict[str, int]:
    with engine.begin() as connection:
        digest_links = connection.execute(
            text("""
            UPDATE core.digest_items di SET item_id = NULL FROM core.digests d
            WHERE di.digest_id = d.id AND di.lane = 'youtube' AND di.item_id IS NOT NULL
              AND d.generated_at <= now() - interval '30 days'
        """)
        ).rowcount
        raw = connection.execute(
            text("""
            DELETE FROM raw.api_responses AS r USING core.sources AS s
            WHERE r.source = s.source
              AND r.fetched_at <= now() -
                  (CASE WHEN r.source = 'youtube' THEN least(s.raw_retention_days, 30)
                        ELSE s.raw_retention_days END) * interval '1 day'
        """)
        ).rowcount
        # Refreshing an item does NOT refresh its old metric observations.
        snapshots = connection.execute(
            text("""
            DELETE FROM core.item_snapshots AS snap USING core.items AS item
            WHERE snap.item_id = item.id AND item.source = 'youtube'
              AND snap.captured_at <= now() - interval '30 days'
        """)
        ).rowcount
        items = connection.execute(
            text("""
            DELETE FROM core.items WHERE source = 'youtube'
                AND last_seen_at <= now() - interval '30 days'
        """)
        ).rowcount
        channels = connection.execute(
            text("""
            DELETE FROM core.youtube_channels
            WHERE refreshed_at <= now() - interval '30 days'
        """)
        ).rowcount
    return {
        "raw_responses": raw,
        "snapshots": snapshots,
        "items": items,
        "channels": channels,
        "digest_links": digest_links,
    }
