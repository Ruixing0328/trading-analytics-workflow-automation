"""Public Vercel endpoint backed exclusively by deterministic synthetic data."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal.dashboard_data import build_dashboard_payload
from notion_trade_journal.dashboard_server import parse_dashboard_filters
from notion_trade_journal.demo_data import build_demo_trade_rows


def build_public_demo_payload(query: str = "") -> dict[str, object]:
    """Build a filtered public payload from synthetic rows only."""

    payload = build_dashboard_payload(build_demo_trade_rows(), parse_dashboard_filters(query))
    payload["source"] = {
        "mode": "demo",
        "label": "Synthetic demo data — illustrative results only",
        "auto_sync": {"enabled": False},
    }
    return payload


class handler(BaseHTTPRequestHandler):
    """Return a shaped analytics payload without reading integration secrets."""

    def do_GET(self) -> None:  # noqa: N802 - Vercel handler hook
        query = urlparse(self.path).query
        payload = build_public_demo_payload(query)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=0, s-maxage=300")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
