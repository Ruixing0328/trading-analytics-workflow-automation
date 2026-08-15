#!/usr/bin/env python3
"""Export the deterministic public demo dataset as inspectable JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal.demo_data import build_demo_trade_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "examples" / "demo_trades.json",
        help="Destination JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"synthetic": True, "trades": build_demo_trade_rows()}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote deterministic synthetic dataset to {output_path}")


if __name__ == "__main__":
    main()
