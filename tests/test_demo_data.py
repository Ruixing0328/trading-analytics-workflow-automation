from __future__ import annotations

import json
from pathlib import Path

from notion_trade_journal.dashboard_data import DashboardFilters, build_dashboard_payload
from notion_trade_journal.demo_data import build_demo_trade_rows

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_demo_rows_are_varied_deterministic_and_public_safe() -> None:
    rows = build_demo_trade_rows()

    assert rows == build_demo_trade_rows()
    assert len(rows) == 48
    assert {"MNQ", "MES"} == {row["instrument"] for row in rows}
    assert {"Win", "Loss", "Breakeven"}.issubset({row["result"] for row in rows})
    assert {"Pre-10:00", "10:00-10:30", "10:30-11:00"} == {row["trade_window"] for row in rows}
    assert {"Papertrade", "Backtest"} == {row["account_type"] for row in rows}
    assert all(row["notion_page_url"] is None for row in rows)
    assert all(row["screenshot_url"] is None for row in rows)
    assert all(row["account_label"] is None for row in rows)
    assert all(str(row["notion_page_id"]).startswith("demo-trade-") for row in rows)


def test_demo_results_are_neutral_and_not_a_profitability_claim() -> None:
    rows = build_demo_trade_rows()
    wins = sum(row["result"] == "Win" for row in rows)
    losses = sum(row["result"] == "Loss" for row in rows)
    win_rate = (wins / (wins + losses)) * 100

    assert 45 <= win_rate <= 55
    assert abs(sum(row["pnl"] for row in rows)) <= 150
    assert max(abs(row["pnl"]) for row in rows) <= 125

    curve = build_dashboard_payload(rows, DashboardFilters())["charts"]["equity_curve"]
    daily_values = [point["daily_pnl"] for point in curve]
    assert any(value > 0 for value in daily_values)
    assert any(value < 0 for value in daily_values)


def test_exported_demo_file_matches_generator() -> None:
    payload = json.loads((PROJECT_ROOT / "examples" / "demo_trades.json").read_text(encoding="utf-8"))

    assert payload["synthetic"] is True
    assert payload["trades"] == build_demo_trade_rows()
