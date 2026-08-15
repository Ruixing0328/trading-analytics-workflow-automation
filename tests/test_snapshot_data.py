from __future__ import annotations

import json

from notion_trade_journal.snapshot_data import load_csv_snapshot_rows, load_json_snapshot_rows, merge_snapshot_rows


def test_merge_snapshot_rows_prefers_supplemental_trade_rows(tmp_path) -> None:
    csv_path = tmp_path / "snapshot.csv"
    csv_path.write_text(
        "trade_name,date,instrument,direction,entry_time,pnl\n"
        "Old Trade,2025-09-26,MNQ,Long,2025-09-26T09:45:00-04:00,10\n",
        encoding="utf-8",
    )
    json_path = tmp_path / "supplement.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "notion_page_id": "page-2026-1",
                    "trade_name": "New Trade",
                    "trade_date": "2026-03-10",
                    "instrument": "MES",
                    "direction": "Short",
                    "entry_time": "2026-03-10T10:08:00-04:00",
                    "pnl": -159.72,
                    "result": "Loss",
                }
            ]
        ),
        encoding="utf-8",
    )

    merged = merge_snapshot_rows(load_csv_snapshot_rows(csv_path), load_json_snapshot_rows(json_path))

    assert len(merged) == 2
    assert any(row.get("trade_date") == "2026-03-10" for row in merged)
    assert any(row.get("trade_date") == "2025-09-26" for row in merged)
