"""Small synchronous request helper for the M3 connectors; never expose responses."""

import logging
import secrets
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from offscroll.connectors._base import ConnectorError

USER_AGENT = "OffscrollBot/0.1 (+https://github.com/sheralimfbads/offscroll/issues)"
logger = logging.getLogger(__name__)


class QuotaError(ConnectorError):
    """Quota exhaustion is safe to report and must not be retried."""


def request_json(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
    reserve: Callable[[], None] | None = None,
) -> dict[str, object]:
    for attempt in range(3):
        # Charge every attempted request, even timeouts and invalid requests.
        if reserve is not None:
            reserve()
        response = None
        try:
            response = client.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT, **(headers or {})},
                timeout=httpx.Timeout(30, connect=5),
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            reason = "timeout"
        except httpx.RequestError:
            raise ConnectorError("Source network request failed.") from None
        else:
            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    raise ConnectorError("Source returned invalid JSON.") from None
                if not isinstance(payload, dict):
                    raise ConnectorError("Source returned an invalid response object.")
                return payload
            if response.status_code == 403:
                # Inspect only Google's structured reason; never surface its message/body.
                try:
                    errors = response.json()["error"]["errors"]
                    quota = any(e.get("reason") == "quotaExceeded" for e in errors)
                except ValueError, KeyError, TypeError, AttributeError:
                    quota = False
                if quota:
                    raise QuotaError("YouTube quotaExceeded; wait for the next quota day.")
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                raise ConnectorError(f"Source request rejected (HTTP {response.status_code}).")
            reason = f"http_{response.status_code}"
        if attempt < 2:
            delay = 5 * 2**attempt + secrets.randbelow(250) / 1000
            if response is not None and (retry_after := response.headers.get("Retry-After")):
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    with suppress(ValueError, TypeError, OverflowError):
                        deadline = parsedate_to_datetime(retry_after)
                        delay = max(
                            delay,
                            (deadline - datetime.now(UTC)).total_seconds(),
                        )
            # Stop rather than ignoring a long server-requested pause.
            if delay > 60:
                raise ConnectorError("Source requests a long retry delay; try again later.")
            logger.warning("event=retry attempt=%s reason=%s", attempt + 1, reason)
            time.sleep(delay)
    raise ConnectorError("Source request failed after 3 attempts.")
