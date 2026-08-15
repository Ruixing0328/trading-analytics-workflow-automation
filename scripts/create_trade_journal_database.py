#!/usr/bin/env python3
"""Create the Trade Journal database in Notion using the project's canonical schema."""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Path to a .env file.")
    parser.add_argument("--title", default="Trade Journal", help="Database title to create.")
    parser.add_argument("--parent-page-id", help="Page ID to create the database under.")
    parser.add_argument("--description", help="Optional database description.")
    parser.add_argument("--inline", action="store_true", help="Create the database inline.")
    parser.add_argument("--log-level", help="Override LOG_LEVEL from .env for this run.")
    return parser.parse_args()


def extract_ids(response: dict) -> dict:
    initial_data_source = response.get("initial_data_source", {})
    data_sources = response.get("data_sources") or []
    return {
        "database_id": response.get("id"),
        "data_source_id": initial_data_source.get("id")
        or response.get("data_source_id")
        or (data_sources[0].get("id") if data_sources else None),
        "url": response.get("url"),
    }


def main() -> None:
    args = parse_args()
    settings = Settings.from_env(args.env_file)
    configure_logging(args.log_level or settings.log_level)

    service = TradeJournalService(settings)
    response = service.create_trade_journal_database(
        title=args.title,
        parent_page_id=args.parent_page_id,
        description=args.description,
        is_inline=args.inline,
    )

    summary = extract_ids(response)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
