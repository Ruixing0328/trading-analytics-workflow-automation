from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_dashboard_uses_curated_assets_and_positioning() -> None:
    index_html = (PROJECT_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    dashboard_js = (PROJECT_ROOT / "dashboard" / "dashboard.js").read_text(encoding="utf-8")
    dashboard_css = (PROJECT_ROOT / "dashboard" / "dashboard.css").read_text(encoding="utf-8")

    assert "Trading Analytics &amp; Workflow Automation Platform" in index_html
    assert "/dashboard.css" in index_html
    assert "/dashboard.js" in index_html
    assert "Data pipelines, integrations, recurring reporting" in index_html
    assert '@import "/base.css";' in dashboard_css
    assert "createClient" not in dashboard_js
    assert "NEXT_PUBLIC_" not in dashboard_js
    assert "/api/config" not in dashboard_js
    assert "trade_journal_dashboard_public" not in dashboard_js
    assert "notion_page_url" not in dashboard_js


def test_removed_dashboard_variants_are_absent() -> None:
    removed = (
        "preview.html", "preview.js", "preview.css", "index.legacy.html",
        "live.js", "live.css", "app.js",
    )
    assert all(not (PROJECT_ROOT / "dashboard" / name).exists() for name in removed)


def test_public_api_is_synthetic_only() -> None:
    api_source = (PROJECT_ROOT / "api" / "dashboard-data.py").read_text(encoding="utf-8")

    assert "build_demo_trade_rows" in api_source
    assert "Synthetic demo data" in api_source
    assert "Settings.from_env" not in api_source
    assert "SupabaseClient" not in api_source
    assert "os.getenv" not in api_source


def test_public_api_filters_synthetic_rows_without_private_fields() -> None:
    module_path = PROJECT_ROOT / "api" / "dashboard-data.py"
    spec = importlib.util.spec_from_file_location("public_dashboard_api", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    payload = module.build_public_demo_payload("account_type=Papertrade")
    serialized = json.dumps(payload)

    assert payload["source"] == {
        "mode": "demo",
        "label": "Synthetic demo data — illustrative results only",
        "auto_sync": {"enabled": False},
    }
    assert payload["filters"]["result_count"] == 24
    assert {row["trade_name"] for row in payload["recent_trades"]}
    assert "notion_page_id" not in serialized
    assert "notion_page_url" not in serialized
    assert "screenshot" not in serialized
    assert "account_label" not in serialized
