from __future__ import annotations

from datetime import date

from notion_trade_journal.daily_results_sync import (
    DailyTradeSummaryRow,
    build_daily_results_page_children,
    build_daily_results_page_properties,
    build_daily_results_summary,
)


def test_build_daily_results_summary_for_complete_day() -> None:
    summary = build_daily_results_summary(
        date(2026, 4, 9),
        [
            DailyTradeSummaryRow(
                page_id="trade-1",
                page_url="https://example.invalid/notion/trade-1",
                trade_name="2026-04-09 MNQ Long 09:40",
                trade_date="2026-04-09",
                instrument="MNQ",
                direction="Long",
                result="Win",
                pnl=194.5,
                entry_time="2026-04-09T09:40:10-04:00",
            )
        ],
    )

    properties = build_daily_results_page_properties(summary)
    children = build_daily_results_page_children(summary)

    assert summary.daily_result == "Win"
    assert summary.net_pnl == 194.5
    assert properties["Net P&L"]["number"] == 194.5
    assert properties["Trade Count"]["number"] == 1.0
    assert children[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Net P&L: +$194.50"
    assert children[-1]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "2026-04-09 MNQ Long 09:40"


def test_build_daily_results_summary_marks_missing_pnl_as_incomplete() -> None:
    summary = build_daily_results_summary(
        date(2025, 9, 4),
        [
            DailyTradeSummaryRow(
                page_id=None,
                page_url=None,
                trade_name="2025-09-04 MNQ Short",
                trade_date="2025-09-04",
                instrument="MNQ",
                direction="Short",
                result="Win",
                pnl=None,
                entry_time=None,
            )
        ],
    )

    properties = build_daily_results_page_properties(summary)
    children = build_daily_results_page_children(summary)

    assert summary.daily_result == "Incomplete"
    assert summary.net_pnl is None
    assert properties["Net P&L"]["number"] is None
    assert properties["Missing P&L Trades"]["number"] == 1.0
    assert children[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Net P&L: incomplete from source data"
    assert children[1]["paragraph"]["rich_text"][0]["text"]["content"] == "Missing P&L Trades: 1"


def test_build_daily_results_summary_marks_breakeven_only_day_as_be() -> None:
    summary = build_daily_results_summary(
        date(2026, 4, 23),
        [
            DailyTradeSummaryRow(
                page_id="trade-1",
                page_url="https://example.invalid/notion/trade-1",
                trade_name="2026-04-23 MNQ Long 09:40 Eval 1",
                trade_date="2026-04-23",
                instrument="MNQ",
                direction="Long",
                result="Breakeven",
                pnl=3.5,
                entry_time="2026-04-23T09:40:20-04:00",
            )
        ],
    )

    properties = build_daily_results_page_properties(summary)

    assert summary.daily_result == "BE"
    assert summary.net_pnl == 3.5
    assert properties["Daily Result"]["select"]["name"] == "BE"
