"""Environment-backed configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .constants import (
    DEFAULT_DASHBOARD_HOST,
    DEFAULT_DAILY_RESULTS_TITLE,
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_DATABASE_TITLE,
    DEFAULT_NOTION_VERSION,
    DEFAULT_SUPABASE_TRADES_TABLE,
    DEFAULT_TIMEZONE,
)
from .exceptions import TradeJournalConfigurationError


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the integration."""

    notion_token: str | None = None
    notion_version: str = DEFAULT_NOTION_VERSION
    trade_journal_name: str = DEFAULT_DATABASE_TITLE
    trade_journal_data_source_id: str | None = None
    trade_journal_parent_page_id: str | None = None
    daily_results_name: str = DEFAULT_DAILY_RESULTS_TITLE
    daily_results_data_source_id: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_trades_table: str = DEFAULT_SUPABASE_TRADES_TABLE
    dashboard_host: str = DEFAULT_DASHBOARD_HOST
    dashboard_port: int = DEFAULT_DASHBOARD_PORT
    dashboard_demo_mode: bool = False
    dashboard_auto_sync_enabled: bool = True
    dashboard_auto_sync_interval_seconds: int = 300
    default_timezone: str = DEFAULT_TIMEZONE
    log_level: str = "INFO"

    @classmethod
    def from_env(
        cls,
        env_file: str | os.PathLike[str] | None = None,
        *,
        require_notion_token: bool = True,
    ) -> "Settings":
        if env_file:
            load_dotenv(Path(env_file))
        else:
            load_dotenv()

        notion_token = os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY")
        if require_notion_token and not notion_token:
            raise TradeJournalConfigurationError(
                "Missing NOTION_TOKEN. Copy .env.example to .env and add your Notion integration token."
            )

        return cls(
            notion_token=notion_token,
            notion_version=os.getenv("NOTION_VERSION", DEFAULT_NOTION_VERSION),
            trade_journal_name=os.getenv("NOTION_TRADE_JOURNAL_NAME", DEFAULT_DATABASE_TITLE),
            trade_journal_data_source_id=os.getenv("NOTION_TRADE_JOURNAL_DATA_SOURCE_ID") or None,
            trade_journal_parent_page_id=os.getenv("NOTION_TRADE_JOURNAL_PARENT_PAGE_ID") or None,
            daily_results_name=os.getenv("NOTION_DAILY_RESULTS_NAME", DEFAULT_DAILY_RESULTS_TITLE),
            daily_results_data_source_id=os.getenv("NOTION_DAILY_RESULTS_DATA_SOURCE_ID") or None,
            supabase_url=os.getenv("SUPABASE_URL") or None,
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or None,
            supabase_trades_table=os.getenv("SUPABASE_TRADES_TABLE", DEFAULT_SUPABASE_TRADES_TABLE),
            dashboard_host=os.getenv("DASHBOARD_HOST", DEFAULT_DASHBOARD_HOST),
            dashboard_port=int(os.getenv("DASHBOARD_PORT", str(DEFAULT_DASHBOARD_PORT))),
            dashboard_demo_mode=(os.getenv("DASHBOARD_DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}),
            dashboard_auto_sync_enabled=(
                os.getenv("DASHBOARD_AUTO_SYNC_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
            ),
            dashboard_auto_sync_interval_seconds=max(
                60,
                int(os.getenv("DASHBOARD_AUTO_SYNC_INTERVAL_SECONDS", "300")),
            ),
            default_timezone=os.getenv("DEFAULT_TIMEZONE", DEFAULT_TIMEZONE),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
