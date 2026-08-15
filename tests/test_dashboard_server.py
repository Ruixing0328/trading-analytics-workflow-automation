from __future__ import annotations

from notion_trade_journal.dashboard_data import DashboardFilters
import json

from notion_trade_journal.config import Settings
from notion_trade_journal.dashboard_server import (
    DashboardAutoSyncManager,
    DashboardDataService,
    select_dashboard_data_service,
)


class SuccessfulSyncService:
    def __init__(self) -> None:
        self.calls = 0

    def sync_trades(self) -> dict:
        self.calls += 1
        return {
            "rows_upserted": 12,
            "pages_read": 12,
            "synced_at": "2026-04-05T12:00:00+00:00",
        }


class FailingSyncService:
    def sync_trades(self) -> dict:
        raise RuntimeError("notion unavailable")


def sample_live_rows() -> list[dict]:
    return [
        {
            "notion_page_id": "page-1",
            "notion_page_url": "https://example.invalid/notion/page-1",
            "trade_name": "2026-04-02 MNQ Long 09:55",
            "trade_date": "2026-04-02",
            "entry_time": "2026-04-02T09:55:00-04:00",
            "instrument": "MNQ",
            "direction": "Long",
            "account_type": "Papertrade",
            "setup_grade": "A+",
            "trade_window": "Pre-10:00",
            "result": "Win",
            "pnl": 211.26,
            "realized_r": 1.29,
            "hold_minutes": 24,
            "emotional_state": "Calm",
        }
    ]


def test_dashboard_auto_sync_manager_tracks_success_and_throttles_requests() -> None:
    sync_service = SuccessfulSyncService()
    manager = DashboardAutoSyncManager(sync_service, interval_seconds=300)

    result = manager.sync_if_due()

    assert result["rows_upserted"] == 12
    assert sync_service.calls == 1
    assert manager.sync_if_due() is None
    assert sync_service.calls == 1
    assert manager.status_snapshot() == {
        "enabled": True,
        "interval_seconds": 300,
        "is_syncing": False,
        "last_attempted_at": manager.last_attempted_at,
        "last_synced_at": "2026-04-05T12:00:00+00:00",
        "last_error": None,
        "rows_upserted": 12,
        "pages_read": 12,
    }


def test_dashboard_data_service_serves_rows_even_if_auto_sync_fails() -> None:
    manager = DashboardAutoSyncManager(FailingSyncService(), interval_seconds=300)
    service = DashboardDataService(
        lambda: sample_live_rows(),
        source_mode="live",
        source_label="Live Notion auto-sync",
        auto_sync_manager=manager,
    )

    payload = service.dashboard_payload(DashboardFilters())

    assert payload["summary"]["total_trades"] == 1
    assert payload["source"]["label"] == "Live Notion auto-sync"
    assert payload["source"]["auto_sync"]["enabled"] is True
    assert payload["source"]["auto_sync"]["last_error"] == "notion unavailable"


def test_dashboard_without_private_credentials_falls_back_to_demo() -> None:
    service = select_dashboard_data_service(Settings(), demo_mode=False)

    payload = service.dashboard_payload(DashboardFilters())

    assert service.source_mode == "demo"
    assert payload["summary"]["total_trades"] == 48
    assert payload["source"]["label"] == "Synthetic demo data — illustrative results only"


def test_explicit_snapshot_mode_never_requires_private_credentials(tmp_path) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(sample_live_rows()), encoding="utf-8")

    service = select_dashboard_data_service(Settings(), snapshot_path=snapshot)
    payload = service.dashboard_payload(DashboardFilters())

    assert service.source_mode == "snapshot"
    assert payload["summary"]["total_trades"] == 1
    assert payload["source"]["label"] == "Explicit local snapshot"
