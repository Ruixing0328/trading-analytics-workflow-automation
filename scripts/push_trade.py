#!/usr/bin/env python3
"""Validate a trade JSON payload and push it into the Notion Trade Journal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal import Settings, TradeJournalService
from notion_trade_journal.logging_utils import configure_logging
from notion_trade_journal.models import load_trade_entry_from_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", help="Path to a JSON file containing one trade payload.")
    parser.add_argument("--env-file", help="Path to a .env file.")
    parser.add_argument("--data-source-id", help="Override the Notion data source ID for this run.")
    parser.add_argument(
        "--duplicate-mode",
        choices=("reject", "skip", "upsert"),
        default="skip",
        help="How to handle an existing trade with the same duplicate key. Default: skip.",
    )
    parser.add_argument(
        "--skip-schema-check",
        action="store_true",
        help="Skip validating the remote Trade Journal schema before creating the page.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the normalized Notion request body without creating anything in Notion.",
    )
    parser.add_argument("--log-level", help="Override LOG_LEVEL from .env for this run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env(args.env_file)
    configure_logging(args.log_level or settings.log_level)

    trade_entry = load_trade_entry_from_json(args.payload)
    service = TradeJournalService(settings)
    response = service.create_trade_entry(
        trade_entry,
        data_source_id=args.data_source_id,
        validate_schema=not args.skip_schema_check,
        dry_run=args.dry_run,
        duplicate_mode=args.duplicate_mode,
    )
    print(json.dumps(response, indent=2, default=str))


if __name__ == "__main__":
    main()
