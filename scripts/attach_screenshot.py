#!/usr/bin/env python3
"""Attach a screenshot to an existing Notion trade page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal import Settings, TradeJournalService
from notion_trade_journal.logging_utils import configure_logging

NOTION_ID_PATTERN = re.compile(
    r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "page",
        help="Notion trade page ID or URL for the row you want to update.",
    )
    parser.add_argument(
        "--file",
        dest="screenshot_path",
        help="Local screenshot file path to upload, such as /path/to/chart.png.",
    )
    parser.add_argument(
        "--url",
        dest="screenshot_url",
        help="Public HTTPS screenshot URL for Notion to import.",
    )
    parser.add_argument("--env-file", help="Path to a .env file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the normalized request body without uploading the file.",
    )
    parser.add_argument("--log-level", help="Override LOG_LEVEL from .env for this run.")
    return parser.parse_args()


def normalize_notion_page_id(raw_value: str) -> str:
    """Extract a Notion page UUID from a raw page ID or full Notion URL."""

    match = NOTION_ID_PATTERN.search(raw_value.strip())
    if not match:
        raise ValueError(f"Could not find a Notion page ID in: {raw_value}")

    compact = match.group(1).replace("-", "").lower()
    return (
        f"{compact[0:8]}-{compact[8:12]}-{compact[12:16]}-"
        f"{compact[16:20]}-{compact[20:32]}"
    )


def main() -> None:
    args = parse_args()
    if bool(args.screenshot_path) == bool(args.screenshot_url):
        raise SystemExit("Provide exactly one of --file or --url.")

    settings = Settings.from_env(args.env_file)
    configure_logging(args.log_level or settings.log_level)

    service = TradeJournalService(settings)
    response = service.update_trade_screenshot(
        normalize_notion_page_id(args.page),
        screenshot_path=args.screenshot_path,
        screenshot_url=args.screenshot_url,
        dry_run=args.dry_run,
    )
    print(json.dumps(response, indent=2, default=str))


if __name__ == "__main__":
    main()
