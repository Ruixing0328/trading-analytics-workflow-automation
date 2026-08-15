"""Minimal Supabase REST client for syncing and reading dashboard data."""

from __future__ import annotations

import logging
from time import sleep
from typing import Any

import requests

from .config import Settings
from .exceptions import SupabaseAPIError, TradeJournalConfigurationError

logger = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
MAX_REQUEST_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 0.5


class SupabaseClient:
    """Small wrapper around Supabase's PostgREST endpoint."""

    def __init__(
        self,
        url: str,
        service_role_key: str,
        *,
        trades_table: str,
        timeout_seconds: int = 30,
    ) -> None:
        if not url:
            raise TradeJournalConfigurationError("SUPABASE_URL is required for Supabase sync and dashboard mode.")
        if not service_role_key:
            raise TradeJournalConfigurationError(
                "SUPABASE_SERVICE_ROLE_KEY is required for Supabase sync and dashboard mode."
            )

        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.trades_table = trades_table
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def retry_delay_seconds(self, attempt: int, *, response: requests.Response | None = None) -> float:
        """Return the sleep duration before retrying a transient Supabase request."""

        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), 0.0)
                except ValueError:
                    pass
        return min(BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)), 2.0)

    @classmethod
    def from_settings(cls, settings: Settings) -> "SupabaseClient":
        return cls(
            settings.supabase_url or "",
            settings.supabase_service_role_key or "",
            trades_table=settings.supabase_trades_table,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Send a request to Supabase and raise a rich exception on failure."""

        url = path if path.startswith("https://") else f"{self.base_url}/{path.lstrip('/')}"
        request_headers = dict(self.session.headers)
        if headers:
            request_headers.update(headers)

        for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json,
                    headers=request_headers,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt >= MAX_REQUEST_ATTEMPTS:
                    raise SupabaseAPIError(f"Request to Supabase failed: {exc}") from exc
                delay_seconds = self.retry_delay_seconds(attempt)
                logger.warning(
                    "Transient Supabase request failure on %s %s (attempt %s/%s): %s. Retrying in %.1fs.",
                    method.upper(),
                    url,
                    attempt,
                    MAX_REQUEST_ATTEMPTS,
                    exc,
                    delay_seconds,
                )
                sleep(delay_seconds)
                continue

            if response.status_code >= 400:
                try:
                    body = response.json()
                except ValueError:
                    body = {"message": response.text}
                details = body.get("details")
                hint = body.get("hint")
                message = body.get("message", f"Supabase API error ({response.status_code})")
                extras = [part for part in (details, hint) if part]
                if extras:
                    message = f"{message} {' '.join(extras)}"
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_REQUEST_ATTEMPTS:
                    delay_seconds = self.retry_delay_seconds(attempt, response=response)
                    logger.warning(
                        "Transient Supabase API error on %s %s (attempt %s/%s): %s. Retrying in %.1fs.",
                        method.upper(),
                        url,
                        attempt,
                        MAX_REQUEST_ATTEMPTS,
                        message,
                        delay_seconds,
                    )
                    sleep(delay_seconds)
                    continue
                raise SupabaseAPIError(
                    message=message,
                    status_code=response.status_code,
                    code=body.get("code"),
                )

            if not response.content:
                return None
            return response.json()

        raise SupabaseAPIError(f"Request to Supabase failed after {MAX_REQUEST_ATTEMPTS} attempts.")

    def fetch_all_trades(
        self,
        *,
        columns: str = "*",
        order: str = "trade_date.desc,entry_time.desc",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch trade rows for dashboard rendering."""

        params: dict[str, Any] = {"select": columns, "order": order}
        if limit is not None:
            params["limit"] = str(limit)
        response = self.request("GET", self.trades_table, params=params)
        return response if isinstance(response, list) else []

    def upsert_trades(
        self,
        records: list[dict[str, Any]],
        *,
        on_conflict: str = "notion_page_id",
    ) -> int:
        """Upsert trade rows into the dashboard table."""

        if not records:
            return 0

        all_keys = sorted({key for record in records for key in record})
        normalized_records = [{key: record.get(key) for key in all_keys} for record in records]

        self.request(
            "POST",
            self.trades_table,
            params={"on_conflict": on_conflict},
            json=normalized_records,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        return len(records)
