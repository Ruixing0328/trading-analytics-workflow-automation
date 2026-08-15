from __future__ import annotations

from notion_trade_journal.supabase_sync import notion_page_to_supabase_record


def test_notion_page_to_supabase_record_flattens_page_properties() -> None:
    page = {
        "id": "00000000-0000-4000-8000-000000000001",
        "url": "https://example.invalid/notion/trade-1",
        "created_time": "2026-04-03T13:00:00.000Z",
        "last_edited_time": "2026-04-03T13:05:00.000Z",
        "properties": {
            "Trade Name": {
                "id": "title",
                "type": "title",
                "title": [{"plain_text": "2026-04-03 MNQ Short 09:42"}],
            },
            "Date": {
                "id": "date",
                "type": "date",
                "date": {"start": "2026-04-03"},
            },
            "Instrument": {
                "id": "instrument",
                "type": "select",
                "select": {"name": "MNQ"},
            },
            "Direction": {
                "id": "direction",
                "type": "select",
                "select": {"name": "Short"},
            },
            "Entry Time": {
                "id": "entry_time",
                "type": "date",
                "date": {"start": "2026-04-03T09:42:00-04:00"},
            },
            "Result": {
                "id": "result",
                "type": "select",
                "select": {"name": "Win"},
            },
            "P&L $": {
                "id": "pnl",
                "type": "number",
                "number": 47.0,
            },
            "A+ Setup": {
                "id": "a_plus_setup",
                "type": "checkbox",
                "checkbox": True,
            },
            "Screenshot": {
                "id": "screenshot",
                "type": "files",
                "files": [
                    {
                        "name": "sample.png",
                        "type": "file",
                        "file": {
                            "url": "https://cdn.example.com/sample.png",
                            "expiry_time": "2026-04-04T13:05:00.000Z",
                        },
                    }
                ],
            },
        },
    }

    record = notion_page_to_supabase_record(page)

    assert record["notion_page_id"] == "00000000-0000-4000-8000-000000000001"
    assert record["trade_name"] == "2026-04-03 MNQ Short 09:42"
    assert record["trade_date"] == "2026-04-03"
    assert record["instrument"] == "MNQ"
    assert record["direction"] == "Short"
    assert record["entry_time"] == "2026-04-03T09:42:00-04:00"
    assert record["result"] == "Win"
    assert record["pnl"] == 47.0
    assert record["a_plus_setup"] is True
    assert record["screenshot_name"] == "sample.png"
    assert record["screenshot_url"] == "https://cdn.example.com/sample.png"
    assert record["screenshot_source"] == "file"


def test_notion_page_to_supabase_record_floors_fractional_hold_minutes() -> None:
    page = {
        "id": "00000000-0000-4000-8000-000000000002",
        "url": "https://example.invalid/notion/trade-2",
        "created_time": "2026-04-07T13:40:00.000Z",
        "last_edited_time": "2026-04-07T13:46:00.000Z",
        "properties": {
            "Trade Name": {
                "id": "title",
                "type": "title",
                "title": [{"plain_text": "2026-04-07 MNQ Short 9:40 AM"}],
            },
            "Date": {
                "id": "date",
                "type": "date",
                "date": {"start": "2026-04-07"},
            },
            "Hold Minutes": {
                "id": "hold_minutes",
                "type": "number",
                "number": 5.33,
            },
        },
    }

    record = notion_page_to_supabase_record(page)

    assert record["hold_minutes"] == 5
