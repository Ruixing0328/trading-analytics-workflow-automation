#!/usr/bin/env python3
"""Import multiple trades from JSON or CSV into the Notion Trade Journal."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal import Settings, TradeJournalService
from notion_trade_journal.logging_utils import configure_logging
from notion_trade_journal.models import load_trade_entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", help="Path to a JSON or CSV batch file.")
    parser.add_argument("--env-file", help="Path to a .env file.")
    parser.add_argument("--data-source-id", help="Override the Notion data source ID for this run.")
    parser.add_argument(
        "--duplicate-mode",
        choices=("reject", "skip", "upsert"),
        default="skip",
        help="How to handle an existing trade with the same duplicate key. Default: skip.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview requests without writing to Notion.")
    parser.add_argument("--skip-schema-check", action="store_true", help="Skip validating the remote schema.")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue processing later trades if one row fails validation or upload.",
    )
    parser.add_argument("--log-level", help="Override LOG_LEVEL from .env for this run.")
    return parser.parse_args()


def load_batch_payloads(input_path: Path) -> list[dict]:
    if input_path.suffix.lower() == ".json":
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        trades = payload if isinstance(payload, list) else payload.get("trades", [])
        if not isinstance(trades, list):
            raise ValueError("JSON batch files must be a list or an object containing a 'trades' list.")
        return trades

    if input_path.suffix.lower() == ".csv":
        rows: list[dict] = []
        with input_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append({key: value for key, value in row.items() if value not in {None, ""}})
        return rows

    raise ValueError("Batch input must be a .json or .csv file.")


def main() -> None:
    args = parse_args()
    settings = Settings.from_env(args.env_file)
    configure_logging(args.log_level or settings.log_level)

    service = TradeJournalService(settings)
    input_path = Path(args.input_file).resolve()
    successes = 0
    failures = 0

    for index, payload in enumerate(load_batch_payloads(input_path), start=1):
        trade_label = payload.get("trade_name") or f"trade {index}"
        try:
            trade_entry = load_trade_entry(payload, base_path=input_path.parent)
            trade_label = trade_entry.trade_name or trade_label
            response = service.create_trade_entry(
                trade_entry,
                data_source_id=args.data_source_id,
                validate_schema=not args.skip_schema_check,
                dry_run=args.dry_run,
                duplicate_mode=args.duplicate_mode,
            )
            action = response.get("action", "ok").upper()
            identifier = response.get("url") or response.get("id") or "dry-run"
            print(f"[{index}] {action} {trade_label} -> {identifier}")
            successes += 1
        except Exception as exc:
            print(f"[{index}] ERROR {trade_label}: {exc}")
            failures += 1
            if not args.continue_on_error:
                raise

    print(json.dumps({"successes": successes, "failures": failures}, indent=2))


if __name__ == "__main__":
    main()
