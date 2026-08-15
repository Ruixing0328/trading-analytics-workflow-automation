#!/usr/bin/env python3
"""Sync the Notion Trade Journal into a Supabase table for analytics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal import Settings, SupabaseSyncService
from notion_trade_journal.logging_utils import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Path to a .env file.")
    parser.add_argument("--data-source-id", help="Override the Notion data source ID for this run.")
    parser.add_argument("--page-size", type=int, default=100, help="How many Notion rows to fetch per API call.")
    parser.add_argument("--batch-size", type=int, default=200, help="How many Supabase rows to upsert at once.")
    parser.add_argument(
        "--skip-schema-check",
        action="store_true",
        help="Skip validating the remote Notion schema before syncing.",
    )
    parser.add_argument("--log-level", help="Override LOG_LEVEL from .env for this run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env(args.env_file)
    configure_logging(args.log_level or settings.log_level)

    service = SupabaseSyncService(settings)
    result = service.sync_trades(
        data_source_id=args.data_source_id,
        validate_schema=not args.skip_schema_check,
        page_size=args.page_size,
        batch_size=args.batch_size,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
