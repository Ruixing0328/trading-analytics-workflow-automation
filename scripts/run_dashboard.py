#!/usr/bin/env python3
"""Run the analytics dashboard in demo, snapshot, or private live mode."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal import Settings
from notion_trade_journal.dashboard_server import serve_dashboard
from notion_trade_journal.logging_utils import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Path to a .env file.")
    parser.add_argument("--host", help="Host to bind the dashboard server to.")
    parser.add_argument("--port", type=int, help="Port to bind the dashboard server to.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use the deterministic synthetic dataset.",
    )
    parser.add_argument(
        "--snapshot",
        help="Use an explicit local .csv or .json snapshot. Never discovered automatically.",
    )
    parser.add_argument("--log-level", help="Override LOG_LEVEL from .env for this run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.demo and args.snapshot:
        raise SystemExit("Choose either --demo or --snapshot, not both.")
    settings = Settings.from_env(args.env_file, require_notion_token=False)
    configure_logging(args.log_level or settings.log_level)
    serve_dashboard(
        settings,
        host=args.host,
        port=args.port,
        demo_mode=True if args.demo else None,
        snapshot_path=args.snapshot,
    )


if __name__ == "__main__":
    main()
