"""Serve the dashboard and its analytics API in explicit data modes."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import Settings
from .dashboard_data import DashboardFilters, build_dashboard_payload
from .demo_data import build_demo_trade_rows
from .snapshot_data import load_csv_snapshot_rows, load_json_snapshot_rows
from .supabase_client import SupabaseClient
from .supabase_sync import SupabaseSyncService

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ASSETS_DIR = PROJECT_ROOT / "dashboard"


class DashboardDataService:
    """Read rows from an explicit source and shape them for the frontend."""

    def __init__(
        self,
        rows_provider: Any,
        *,
        source_mode: str,
        source_label: str,
        auto_sync_manager: "DashboardAutoSyncManager | None" = None,
    ) -> None:
        self.rows_provider = rows_provider
        self.source_mode = source_mode
        self.source_label = source_label
        self.auto_sync_manager = auto_sync_manager

    def dashboard_payload(self, filters: DashboardFilters) -> dict[str, Any]:
        if self.auto_sync_manager:
            try:
                self.auto_sync_manager.sync_if_due()
            except Exception:  # pragma: no cover - exercised manually
                logger.warning("Automatic sync failed; serving the latest Supabase snapshot.", exc_info=True)
        payload = build_dashboard_payload(self.rows_provider(), filters)
        payload["source"] = {
            "mode": self.source_mode,
            "label": self.source_label,
            "auto_sync": self.auto_sync_manager.status_snapshot() if self.auto_sync_manager else {"enabled": False},
        }
        return payload

    def warm_source(self) -> None:
        if not self.auto_sync_manager:
            return
        try:
            self.auto_sync_manager.sync_if_due(force=True)
        except Exception:  # pragma: no cover - exercised manually
            logger.warning("Initial sync failed; continuing with the latest Supabase snapshot.", exc_info=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return datetime.fromisoformat(text)


class DashboardAutoSyncManager:
    """Throttle on-demand Notion-to-Supabase refreshes."""

    def __init__(self, sync_service: SupabaseSyncService, *, interval_seconds: int) -> None:
        self.sync_service = sync_service
        self.interval_seconds = max(60, interval_seconds)
        self._lock = Lock()
        self.last_attempted_at: str | None = None
        self.last_synced_at: str | None = None
        self.last_result: dict[str, Any] | None = None
        self.last_error: str | None = None

    def sync_due(self) -> bool:
        last_attempted = parse_utc_iso(self.last_attempted_at)
        if last_attempted is None:
            return True
        return (datetime.now(timezone.utc) - last_attempted).total_seconds() >= self.interval_seconds

    def sync_if_due(self, *, force: bool = False) -> dict[str, Any] | None:
        if not force and not self.sync_due():
            return None
        return self.sync_now()

    def sync_now(self) -> dict[str, Any] | None:
        if not self._lock.acquire(blocking=False):
            return None
        self.last_attempted_at = utc_now_iso()
        self.last_error = None
        try:
            result = self.sync_service.sync_trades()
            self.last_result = result
            self.last_synced_at = result.get("synced_at") or utc_now_iso()
            return result
        except Exception as exc:
            self.last_error = str(exc)
            raise
        finally:
            self._lock.release()

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "interval_seconds": self.interval_seconds,
            "is_syncing": self._lock.locked(),
            "last_attempted_at": self.last_attempted_at,
            "last_synced_at": self.last_synced_at,
            "last_error": self.last_error,
            "rows_upserted": (self.last_result or {}).get("rows_upserted"),
            "pages_read": (self.last_result or {}).get("pages_read"),
        }


def build_supabase_data_service(settings: Settings) -> DashboardDataService:
    supabase_client = SupabaseClient.from_settings(settings)
    auto_sync_manager: DashboardAutoSyncManager | None = None
    source_label = "Private Supabase snapshot"
    if settings.dashboard_auto_sync_enabled and settings.notion_token:
        auto_sync_manager = DashboardAutoSyncManager(
            SupabaseSyncService(settings, supabase_client=supabase_client),
            interval_seconds=settings.dashboard_auto_sync_interval_seconds,
        )
        source_label = "Private Notion-to-Supabase auto-sync"
    return DashboardDataService(
        supabase_client.fetch_all_trades,
        source_mode="live",
        source_label=source_label,
        auto_sync_manager=auto_sync_manager,
    )


def build_demo_data_service() -> DashboardDataService:
    return DashboardDataService(
        build_demo_trade_rows,
        source_mode="demo",
        source_label="Synthetic demo data — illustrative results only",
    )


def build_snapshot_data_service(snapshot_path: str | Path) -> DashboardDataService:
    path = Path(snapshot_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Snapshot file not found: {path}")
    if path.suffix.casefold() == ".csv":
        rows_provider = lambda: load_csv_snapshot_rows(path)
    elif path.suffix.casefold() == ".json":
        rows_provider = lambda: load_json_snapshot_rows(path)
    else:
        raise ValueError("Snapshot mode supports .csv or .json files.")
    return DashboardDataService(
        rows_provider,
        source_mode="snapshot",
        source_label="Explicit local snapshot",
    )


def select_dashboard_data_service(
    settings: Settings,
    *,
    demo_mode: bool | None = None,
    snapshot_path: str | Path | None = None,
) -> DashboardDataService:
    """Select an explicit source, using synthetic data as the safe fallback."""

    use_demo_mode = settings.dashboard_demo_mode if demo_mode is None else demo_mode
    if use_demo_mode:
        return build_demo_data_service()
    if snapshot_path:
        return build_snapshot_data_service(snapshot_path)
    if settings.supabase_url and settings.supabase_service_role_key:
        return build_supabase_data_service(settings)
    logger.info("No private data source configured; falling back to the synthetic demo.")
    return build_demo_data_service()


def parse_dashboard_filters(query: str) -> DashboardFilters:
    params = parse_qs(query)

    def pick(key: str) -> str | None:
        values = params.get(key)
        if not values:
            return None
        return values[0].strip() or None

    return DashboardFilters(
        start_date=pick("start_date"),
        end_date=pick("end_date"),
        instrument=pick("instrument"),
        account_type=pick("account_type"),
        setup_grade=pick("setup_grade"),
        result=pick("result"),
    )


def make_handler(data_service: DashboardDataService) -> type[SimpleHTTPRequestHandler]:
    class DashboardHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(DASHBOARD_ASSETS_DIR), **kwargs)

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self.respond_json({"ok": True}, status=HTTPStatus.OK)
                return
            if parsed.path == "/api/dashboard-data":
                try:
                    payload = data_service.dashboard_payload(parse_dashboard_filters(parsed.query))
                    payload["filters"]["active"] = asdict(parse_dashboard_filters(parsed.query))
                    self.respond_json(payload, status=HTTPStatus.OK)
                except Exception as exc:  # pragma: no cover - exercised manually
                    logger.exception("Dashboard API request failed")
                    self.respond_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if parsed.path == "/":
                self.path = "/index.html"
            super().do_GET()

        def respond_json(self, payload: dict[str, Any], *, status: HTTPStatus) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:
            logger.info("%s - %s", self.address_string(), format % args)

    return DashboardHandler


def serve_dashboard(
    settings: Settings,
    *,
    host: str | None = None,
    port: int | None = None,
    demo_mode: bool | None = None,
    snapshot_path: str | Path | None = None,
) -> None:
    """Start the dashboard using demo, explicit snapshot, or private live data."""

    server_host = host or settings.dashboard_host
    server_port = port or settings.dashboard_port
    data_service = select_dashboard_data_service(
        settings,
        demo_mode=demo_mode,
        snapshot_path=snapshot_path,
    )

    data_service.warm_source()
    server = ThreadingHTTPServer((server_host, server_port), make_handler(data_service))
    logger.info("Dashboard available at http://%s:%s (%s)", server_host, server_port, data_service.source_label)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping dashboard server.")
    finally:
        server.server_close()
