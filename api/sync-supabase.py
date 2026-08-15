from __future__ import annotations

"""Bearer-protected sync endpoint for private deployments only.

The public demo does not configure this endpoint with credentials or schedule it.
See deployment/vercel.private-cron.example.json for the private cron reference.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from notion_trade_journal import Settings, SupabaseSyncService
from notion_trade_journal.exceptions import TradeJournalConfigurationError
from notion_trade_journal.logging_utils import configure_logging


def json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        cron_secret = (os.getenv("CRON_SECRET") or "").strip()
        auth_header = self.headers.get("authorization")
        if not cron_secret or auth_header != f"Bearer {cron_secret}":
            self.send_json(
                401,
                {
                    "ok": False,
                    "error": "Unauthorized.",
                },
            )
            return

        try:
            settings = Settings.from_env()
            configure_logging(settings.log_level)
            result = SupabaseSyncService(settings).sync_trades()
        except TradeJournalConfigurationError as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:  # pragma: no cover - exercised in deployment
            self.send_json(500, {"ok": False, "error": str(exc)})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "result": result,
            },
        )
