from __future__ import annotations

from notion_trade_journal.mapping import build_notion_page_properties
from notion_trade_journal.models import TradeEntry
from notion_trade_journal.schema import build_data_source_properties


def sample_trade() -> TradeEntry:
    return TradeEntry.model_validate(
        {
            "date": "2026-04-03",
            "instrument": "MNQ",
            "direction": "Short",
            "account_type": "Funded",
            "entry_time": "2026-04-03T09:42:00-04:00",
            "result": "Win",
            "pnl": 47.0,
            "entry_rationale": "Clean short entry.",
            "what_went_well": "",
        }
    )


def test_build_notion_page_properties_maps_core_fields() -> None:
    properties = build_notion_page_properties(sample_trade(), screenshot_upload_id="upload-123", screenshot_name="chart.png")

    assert properties["Trade Name"]["title"][0]["text"]["content"] == "2026-04-03 MNQ Short 09:42"
    assert properties["Instrument"]["select"]["name"] == "MNQ"
    assert properties["Direction"]["select"]["name"] == "Short"
    assert properties["Account Type"]["select"]["name"] == "Funded"
    assert properties["Trade Window"]["select"]["name"] == "Pre-10:00"
    assert properties["Result"]["select"]["name"] == "Win"
    assert properties["P&L $"]["number"] == 47.0
    assert properties["Entry Rationale"]["rich_text"][0]["text"]["content"] == "Clean short entry."
    assert properties["Screenshot"]["files"][0]["file_upload"]["id"] == "upload-123"
    assert "What Went Well" not in properties


def test_build_data_source_properties_contains_expected_types() -> None:
    schema = build_data_source_properties()

    assert schema["Trade Name"] == {"title": {}}
    assert schema["Date"] == {"date": {}}
    assert schema["Screenshot"] == {"files": {}}
    assert schema["P&L $"] == {"number": {"format": "dollar"}}
    assert [option["name"] for option in schema["Account Type"]["select"]["options"]] == [
        "Funded",
        "Eval",
        "Backtest",
        "Papertrade",
    ]


def test_build_notion_page_properties_omits_blank_time_fields() -> None:
    trade = TradeEntry.model_validate(
        {
            "date": "2025-07-15",
            "instrument": "MNQ",
            "direction": "Short",
            "result": "Loss",
            "pnl": -10.0,
        }
    )

    properties = build_notion_page_properties(trade)

    assert properties["Trade Name"]["title"][0]["text"]["content"] == "2025-07-15 MNQ Short"
    assert "Entry Time" not in properties
    assert "Trade Window" not in properties
    assert "Hold Minutes" not in properties
