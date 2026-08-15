from __future__ import annotations

from notion_trade_journal.dashboard_data import (
    DashboardFilters,
    build_dashboard_payload,
    compute_win_rate,
)
from notion_trade_journal.demo_data import build_demo_trade_rows


def test_win_rate_excludes_breakeven_records() -> None:
    assert compute_win_rate(2, 2) == 50
    assert compute_win_rate(0, 0) is None


def test_dashboard_payload_contains_recruiter_facing_metrics() -> None:
    payload = build_dashboard_payload(build_demo_trade_rows(), DashboardFilters())

    assert payload["summary"]["total_trades"] == 48
    assert payload["summary"]["total_pnl"] == 35
    assert 45 <= payload["summary"]["win_rate"] <= 55
    assert payload["summary"]["profit_factor"] is not None
    assert payload["scorecards"]["weekly"]
    assert payload["scorecards"]["monthly"]
    assert payload["charts"]["equity_curve"]
    assert {row["label"] for row in payload["charts"]["by_instrument"]} == {"MNQ", "MES"}
    assert payload["charts"]["discipline_flags"]
    assert len(payload["recent_trades"]) == 12
    assert "labs" not in payload


def test_dashboard_filters_are_applied_without_changing_available_values() -> None:
    payload = build_dashboard_payload(
        build_demo_trade_rows(),
        DashboardFilters(account_type="Papertrade", instrument="MNQ"),
    )

    assert 0 < payload["filters"]["result_count"] < payload["filters"]["source_count"]
    assert payload["filters"]["available"]["account_type"] == ["Backtest", "Papertrade"]
    assert all(row["instrument"] == "MNQ" for row in payload["recent_trades"])


def test_empty_filter_result_returns_stable_payload() -> None:
    payload = build_dashboard_payload(
        build_demo_trade_rows(),
        DashboardFilters(instrument="DOES-NOT-EXIST"),
    )

    assert payload["summary"]["total_trades"] == 0
    assert payload["charts"]["equity_curve"] == []
    assert payload["recent_trades"] == []
