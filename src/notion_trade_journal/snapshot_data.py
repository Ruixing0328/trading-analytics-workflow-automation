"""Read explicit local trade-journal snapshots for dashboard analysis."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_csv_snapshot_rows(csv_path: str | Path) -> list[dict[str, Any]]:
    """Load the generated historical CSV into dashboard-friendly row dicts."""

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Snapshot CSV not found: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cleaned = {key: value for key, value in row.items() if value not in {None, ""}}
            cleaned["notion_page_url"] = None
            cleaned["notion_page_id"] = cleaned.get("source_trade_id") or cleaned.get("trade_name") or path.stem
            cleaned["trade_date"] = cleaned.get("date")
            rows.append(cleaned)
    return rows


def load_json_snapshot_rows(json_path: str | Path) -> list[dict[str, Any]]:
    """Load a JSON snapshot supplement into dashboard-friendly row dicts."""

    path = Path(json_path)
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Snapshot JSON must be a list of row objects: {path}")

    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        cleaned = {key: value for key, value in item.items() if value not in {None, ""}}
        cleaned["trade_date"] = cleaned.get("trade_date") or cleaned.get("date")
        rows.append(cleaned)
    return rows


def merge_snapshot_rows(*row_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge multiple row lists, preferring later rows on duplicate IDs."""

    merged: dict[str, dict[str, Any]] = {}
    for rows in row_sets:
        for row in rows:
            key = str(
                row.get("notion_page_id")
                or row.get("notion_page_url")
                or row.get("trade_name")
                or f"{row.get('trade_date')}|{row.get('instrument')}|{row.get('entry_time')}"
            )
            merged[key] = dict(row)
    return list(merged.values())
