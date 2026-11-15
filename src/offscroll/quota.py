"""Reserve API units durably before requests; rollbacks must not refund quota."""

from dataclasses import dataclass

from sqlalchemy import Engine, text

from offscroll.connectors._http import QuotaError


@dataclass
class YouTubeQuota:
    engine: Engine
    units: int = 0

    def reserve(self) -> None:
        # Separate transaction: failed runs and concurrent workers still consume quota.
        with self.engine.begin() as connection:
            reserved = connection.execute(
                text("""
                INSERT INTO raw.api_quota_usage (date, source, units)
                VALUES ((clock_timestamp() AT TIME ZONE 'America/Los_Angeles')::date,
                        'youtube', 1)
                ON CONFLICT (date, source) DO UPDATE
                    SET units = raw.api_quota_usage.units + 1
                    WHERE raw.api_quota_usage.units + 1 < 8000
                RETURNING units
            """)
            ).scalar_one_or_none()
            if reserved is None:
                raise QuotaError("YouTube local daily quota guard reached; no request sent.")
        self.units += 1
