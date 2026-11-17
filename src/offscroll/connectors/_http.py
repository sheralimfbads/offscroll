"""Small synchronous request helper for the M3 connectors; never expose responses."""

import logging
import math
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


GOOGLE_REASONS = frozenset(
    {
        "quotaExceeded",
        "dailyLimitExceeded",
        "keyInvalid",
        "keyExpired",
        "accessNotConfigured",
        "ipRefererBlocked",
        "forbidden",
        "API_KEY_INVALID",
        "API_KEY_EXPIRED",
        "API_KEY_SERVICE_BLOCKED",
        "API_KEY_HTTP_REFERRER_BLOCKED",
        "API_KEY_IP_ADDRESS_BLOCKED",
        "SERVICE_DISABLED",
    }
)


def google_error_reason(response: httpx.Response) -> str | None:
    """Return only an allowlisted reason, never messages, metadata, URLs or keys."""
    try:
        error = response.json()["error"]
        reasons = [
            entry.get("reason")
            for field in ("errors", "details")
            for entry in error.get(field, [])
            if isinstance(entry, dict)
        ]
        for value in reasons:
            if isinstance(value, str) and value in GOOGLE_REASONS:
                return value
    except ValueError, KeyError, TypeError, AttributeError:
        pass
    return None


def retry_delay(response: httpx.Response | None, default: float) -> float:
    delay = default
    if response is not None and (header := response.headers.get("Retry-After")):
        try:
            requested = float(header)
        except ValueError:
            with suppress(ValueError, TypeError, OverflowError):
                requested = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
                delay = max(delay, requested)
        else:
            if not math.isfinite(requested):
                raise ConnectorError("Source returned an invalid retry delay.")
            delay = max(delay, requested)
    if not math.isfinite(delay) or delay > 60:
        raise ConnectorError("Source requests a long retry delay; try again later.")
    return delay


class QuotaError(ConnectorError):
    """Quota exhaustion is safe to report and must not be retried."""


class SourceHTTPError(ConnectorError):
    """Expose only a numeric HTTP status, never the response message or URL."""

    def __init__(self, status_code: int, reason: str | None = None) -> None:
        self.reason = reason if reason in GOOGLE_REASONS else None
        self.status_code = status_code
        super().__init__(f"Source request rejected (HTTP {status_code}).")


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
            api_reason = google_error_reason(response)
            if api_reason in {"quotaExceeded", "dailyLimitExceeded"}:
                raise QuotaError(f"YouTube {api_reason}; wait for the next quota day.")
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                raise SourceHTTPError(response.status_code, api_reason)
            reason = f"http_{response.status_code}"
        if attempt < 2:
            delay = retry_delay(response, 5 * 2**attempt + secrets.randbelow(250) / 1000)
            logger.warning("event=retry attempt=%s reason=%s", attempt + 1, reason)
            time.sleep(delay)
    raise ConnectorError("Source request failed after 3 attempts.")
