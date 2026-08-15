"""High-level service for database setup and trade entry ingestion."""

from __future__ import annotations

from datetime import date
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Literal

from .config import Settings
from .constants import DEFAULT_DAILY_RESULTS_TITLE, DEFAULT_DATABASE_TITLE
from .daily_results_sync import (
    build_daily_results_page_children,
    build_daily_results_page_properties,
    build_daily_results_summary,
    trade_summary_row_from_page,
)
from .mapping import build_notion_page_properties, build_screenshot_property
from .models import TradeEntry
from .notion_client import NotionClient
from .schema import build_data_source_properties, expected_property_map
from .supabase_client import SupabaseClient
from .exceptions import (
    TradeJournalConfigurationError,
    TradeJournalDuplicateError,
    TradeJournalSchemaError,
    TradeJournalSyncError,
)

logger = logging.getLogger(__name__)

DUPLICATE_MODES = {"reject", "skip", "upsert"}


def _select_filter_value(value: Any) -> str:
    return str(value.value if isinstance(value, Enum) else value)


class TradeJournalService:
    """Coordinates validation, schema checks, file uploads, and page creation."""

    def __init__(
        self,
        settings: Settings,
        client: NotionClient | None = None,
        *,
        supabase_client: SupabaseClient | None = None,
    ):
        self.settings = settings
        self.client = client or NotionClient(
            token=settings.notion_token,
            notion_version=settings.notion_version,
        )
        self.supabase_client = supabase_client
        if self.supabase_client is None and settings.supabase_url and settings.supabase_service_role_key:
            self.supabase_client = SupabaseClient.from_settings(settings)

    def resolve_data_source_id(self, explicit_data_source_id: str | None = None) -> str:
        """Resolve the target data source ID from CLI args, env, or Notion search."""

        if explicit_data_source_id:
            return explicit_data_source_id
        if self.settings.trade_journal_data_source_id:
            return self.settings.trade_journal_data_source_id

        journal_name = self.settings.trade_journal_name or DEFAULT_DATABASE_TITLE
        match = self.client.find_data_source_by_title(journal_name)
        if match:
            return match["id"]

        raise TradeJournalConfigurationError(
            f"Could not locate a shared Notion data source named '{journal_name}'. "
            "Set NOTION_TRADE_JOURNAL_DATA_SOURCE_ID or share the Trade Journal database with the integration."
        )

    def validate_data_source_schema(self, data_source_id: str) -> dict[str, Any]:
        """Ensure the Trade Journal schema in Notion matches the code's expected schema."""

        data_source = self.client.retrieve_data_source(data_source_id)
        actual_properties = data_source.get("properties", {})
        expected_properties = expected_property_map()

        missing = [name for name in expected_properties if name not in actual_properties]
        type_mismatches: list[str] = []
        missing_options: list[str] = []

        for name, definition in expected_properties.items():
            actual = actual_properties.get(name)
            if not actual:
                continue
            actual_type = actual.get("type")
            if actual_type != definition.notion_type:
                type_mismatches.append(f"{name}: expected {definition.notion_type}, got {actual_type}")
                continue

            if definition.options:
                actual_options = {option["name"] for option in actual[actual_type].get("options", [])}
                required_options = {option.name for option in definition.options}
                missing_from_schema = sorted(required_options - actual_options)
                if missing_from_schema:
                    missing_options.append(f"{name}: missing {', '.join(missing_from_schema)}")

        if missing or type_mismatches or missing_options:
            lines = ["Trade Journal schema mismatch detected."]
            if missing:
                lines.append(f"Missing properties: {', '.join(sorted(missing))}")
            if type_mismatches:
                lines.append("Type mismatches: " + "; ".join(type_mismatches))
            if missing_options:
                lines.append("Missing select options: " + "; ".join(missing_options))
            raise TradeJournalSchemaError(" ".join(lines))

        return data_source

    def create_trade_journal_database(
        self,
        *,
        title: str = DEFAULT_DATABASE_TITLE,
        parent_page_id: str | None = None,
        description: str | None = None,
        is_inline: bool = False,
    ) -> dict[str, Any]:
        """Create the Trade Journal database using the project's canonical schema."""

        parent_id = parent_page_id or self.settings.trade_journal_parent_page_id
        schema = build_data_source_properties()
        response = self.client.create_database(
            title=title,
            properties=schema,
            parent_page_id=parent_id,
            description=description,
            is_inline=is_inline,
        )
        return response

    def resolve_daily_results_data_source_id(self, explicit_data_source_id: str | None = None) -> str | None:
        """Resolve the Daily Results data source from args, env, or a title search."""

        if explicit_data_source_id:
            return explicit_data_source_id
        if self.settings.daily_results_data_source_id:
            return self.settings.daily_results_data_source_id

        daily_results_name = self.settings.daily_results_name or DEFAULT_DAILY_RESULTS_TITLE
        match = self.client.find_data_source_by_title(daily_results_name)
        if match:
            return match["id"]
        return None

    def find_daily_results_page(self, data_source_id: str, trade_date: date) -> dict[str, Any] | None:
        """Find the Daily Results page for the requested session date."""

        response = self.client.query_data_source(
            data_source_id,
            filter_payload={"property": "Date", "date": {"equals": trade_date.isoformat()}},
            page_size=2,
        )
        matches = response.get("results", [])
        if len(matches) > 1:
            raise TradeJournalSyncError(
                f"Multiple Daily Results pages exist for {trade_date.isoformat()}. Resolve the duplicates in Notion first."
            )
        return matches[0] if matches else None

    def trade_pages_for_date(
        self,
        trade_date: date,
        *,
        trade_journal_data_source_id: str,
        ensure_page_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load the Trade Journal rows for one date in newest-first order."""

        pages = self.client.iterate_data_source_pages(
            trade_journal_data_source_id,
            filter_payload={"property": "Date", "date": {"equals": trade_date.isoformat()}},
            sorts=[{"property": "Entry Time", "direction": "descending"}],
            page_size=100,
        )
        if ensure_page_id and all(page.get("id") != ensure_page_id for page in pages):
            ensured_page = self.client.retrieve_page(ensure_page_id)
            pages.append(ensured_page)
            pages.sort(
                key=lambda page: (
                    page.get("properties", {}).get("Entry Time", {}).get("date", {}).get("start") or "",
                    page.get("id") or "",
                ),
                reverse=True,
            )
        return pages

    def sync_daily_results_for_date(
        self,
        trade_date: date,
        *,
        trade_journal_data_source_id: str,
        ensure_trade_page_id: str | None = None,
        daily_results_data_source_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Create or update the Notion Daily Results row that corresponds to the trade date."""

        resolved_daily_results_id = self.resolve_daily_results_data_source_id(daily_results_data_source_id)
        if not resolved_daily_results_id:
            return None

        trade_pages = self.trade_pages_for_date(
            trade_date,
            trade_journal_data_source_id=trade_journal_data_source_id,
            ensure_page_id=ensure_trade_page_id,
        )
        if not trade_pages:
            raise TradeJournalSyncError(
                f"No Trade Journal rows were found for {trade_date.isoformat()} while syncing Daily Results."
            )

        summary = build_daily_results_summary(
            trade_date,
            [trade_summary_row_from_page(page) for page in trade_pages],
        )
        properties = build_daily_results_page_properties(summary)
        children = build_daily_results_page_children(summary)
        existing_page = self.find_daily_results_page(resolved_daily_results_id, trade_date)

        if existing_page:
            response = self.client.update_page(existing_page["id"], properties)
            self.client.replace_page_children(existing_page["id"], children)
            return {
                "action": "updated",
                "id": existing_page.get("id"),
                "url": existing_page.get("url"),
                "trade_count": summary.trade_count,
                "daily_result": summary.daily_result,
            }

        response = self.client.create_page(
            resolved_daily_results_id,
            properties,
            children=children,
        )
        return {
            "action": "created",
            "id": response.get("id"),
            "url": response.get("url"),
            "trade_count": summary.trade_count,
            "daily_result": summary.daily_result,
        }

    def sync_page_to_supabase(self, page: dict[str, Any]) -> dict[str, Any] | None:
        """Upsert one saved trade page into Supabase so dashboard totals refresh immediately."""

        if self.supabase_client is None:
            return None

        page_for_sync = page
        if not page_for_sync.get("properties"):
            page_id = page_for_sync.get("id")
            if not page_id:
                raise TradeJournalSyncError(
                    "The saved Notion page could not be reloaded for the Supabase daily-results sync."
                )
            page_for_sync = self.client.retrieve_page(page_id)

        from .supabase_sync import notion_page_to_supabase_record

        rows_upserted = self.supabase_client.upsert_trades([notion_page_to_supabase_record(page_for_sync)])
        return {
            "rows_upserted": rows_upserted,
            "table": self.supabase_client.trades_table,
        }

    def sync_downstream_targets(
        self,
        trade_entry: TradeEntry,
        trade_page: dict[str, Any],
        *,
        trade_journal_data_source_id: str,
    ) -> dict[str, Any]:
        """Keep secondary destinations aligned after a Trade Journal write succeeds."""

        location = trade_page.get("url") or trade_page.get("id") or "unknown page"
        sync_details: dict[str, Any] = {}

        try:
            daily_results_sync = self.sync_daily_results_for_date(
                trade_entry.date,
                trade_journal_data_source_id=trade_journal_data_source_id,
                ensure_trade_page_id=trade_page.get("id"),
            )
        except Exception as exc:
            raise TradeJournalSyncError(
                f"Trade journal entry saved in Notion at {location}, but syncing the Notion Daily Results page failed: {exc}"
            ) from exc
        if daily_results_sync is not None:
            sync_details["daily_results"] = daily_results_sync

        try:
            supabase_sync = self.sync_page_to_supabase(trade_page)
        except Exception as exc:
            raise TradeJournalSyncError(
                f"Trade journal entry saved in Notion at {location}, but syncing Supabase failed: {exc}"
            ) from exc
        if supabase_sync is not None:
            sync_details["supabase"] = supabase_sync
        return sync_details

    def prepare_screenshot_upload(
        self,
        *,
        screenshot_path: str | None = None,
        screenshot_url: str | None = None,
        dry_run: bool = False,
    ) -> tuple[str | None, str | None, dict[str, Any] | None]:
        """Upload or preview one screenshot attachment for a Notion page property."""

        if screenshot_path and screenshot_url:
            raise ValueError("Use either screenshot_path or screenshot_url, not both.")

        screenshot_upload_id: str | None = None
        screenshot_name: str | None = None
        attachment_preview: dict[str, Any] | None = None

        if dry_run and screenshot_path:
            screenshot_name = Path(screenshot_path).name
            attachment_preview = {"mode": "local_file", "path": screenshot_path}
        elif dry_run and screenshot_url:
            screenshot_name = screenshot_url.rstrip("/").split("/")[-1] or "screenshot"
            attachment_preview = {"mode": "external_url", "url": screenshot_url}
        elif screenshot_path:
            uploaded_file = self.client.upload_local_file(Path(screenshot_path))
            screenshot_upload_id = uploaded_file["id"]
            screenshot_name = uploaded_file.get("filename")
        elif screenshot_url:
            uploaded_file = self.client.import_external_file(screenshot_url)
            screenshot_upload_id = uploaded_file["id"]
            screenshot_name = uploaded_file.get("filename")

        return screenshot_upload_id, screenshot_name, attachment_preview

    def update_trade_screenshot(
        self,
        page_id: str,
        *,
        screenshot_path: str | None = None,
        screenshot_url: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Attach one screenshot to an existing trade page and refresh downstream syncs."""

        screenshot_upload_id, screenshot_name, attachment_preview = self.prepare_screenshot_upload(
            screenshot_path=screenshot_path,
            screenshot_url=screenshot_url,
            dry_run=dry_run,
        )

        if screenshot_upload_id is None and attachment_preview is None:
            raise ValueError("Provide screenshot_path or screenshot_url.")

        properties = (
            build_screenshot_property(screenshot_upload_id, screenshot_name=screenshot_name)
            if screenshot_upload_id
            else {}
        )

        response: dict[str, Any] = {
            "action": "updated",
            "page_id": page_id,
            "properties": properties,
        }
        if dry_run:
            if attachment_preview:
                response["attachment_preview"] = attachment_preview
                response["attachment_note"] = (
                    "Dry-run mode does not upload files. The Screenshot property will be populated after a live run."
                )
            return response

        updated_page = self.client.update_page(page_id, properties)
        refreshed_page = self.client.retrieve_page(page_id)
        result = {
            "action": "updated",
            "id": updated_page.get("id", page_id),
            "url": updated_page.get("url") or refreshed_page.get("url"),
        }
        supabase_sync = self.sync_page_to_supabase(refreshed_page)
        if supabase_sync is not None:
            result["sync"] = {"supabase": supabase_sync}
        return result

    def find_duplicate_trade_entry(
        self,
        data_source_id: str,
        trade_entry: TradeEntry,
    ) -> dict[str, Any] | None:
        """Find an existing page that matches the trade's duplicate key."""

        # Historical backfills can intentionally omit Entry Time. In that case we
        # avoid guessing a weaker duplicate key that could collapse distinct rows.
        if trade_entry.entry_time is None:
            return None

        filter_payload = {
            "and": [
                {"property": "Date", "date": {"equals": trade_entry.date.isoformat()}},
                {"property": "Instrument", "select": {"equals": _select_filter_value(trade_entry.instrument)}},
                {"property": "Direction", "select": {"equals": _select_filter_value(trade_entry.direction)}},
                {"property": "Entry Time", "date": {"equals": trade_entry.entry_time.isoformat()}},
            ]
        }
        if trade_entry.account_type:
            filter_payload["and"].append(
                {"property": "Account Type", "select": {"equals": _select_filter_value(trade_entry.account_type)}}
            )
        if trade_entry.account_label:
            filter_payload["and"].append(
                {"property": "Account Label", "rich_text": {"equals": trade_entry.account_label}}
            )
        response = self.client.query_data_source(
            data_source_id,
            filter_payload=filter_payload,
            page_size=2,
        )
        matches = response.get("results", [])
        if len(matches) > 1:
            raise TradeJournalDuplicateError(
                "Multiple existing trades match the duplicate key "
                f"({trade_entry.date.isoformat()}, {trade_entry.instrument}, {trade_entry.direction}, "
                f"{trade_entry.entry_time.isoformat()}). Resolve the duplicates in Notion before uploading again."
            )
        return matches[0] if matches else None

    def create_trade_entry(
        self,
        trade_entry: TradeEntry,
        *,
        data_source_id: str | None = None,
        validate_schema: bool = True,
        dry_run: bool = False,
        duplicate_mode: Literal["reject", "skip", "upsert"] = "skip",
    ) -> dict[str, Any]:
        """Upload an optional screenshot and create the trade page in Notion."""

        if duplicate_mode not in DUPLICATE_MODES:
            raise ValueError(
                f"Unsupported duplicate_mode '{duplicate_mode}'. Expected one of: {', '.join(sorted(DUPLICATE_MODES))}."
            )

        resolved_data_source_id = self.resolve_data_source_id(data_source_id)
        if validate_schema:
            self.validate_data_source_schema(resolved_data_source_id)

        existing_page = self.find_duplicate_trade_entry(resolved_data_source_id, trade_entry)
        if existing_page and duplicate_mode == "reject":
            raise TradeJournalDuplicateError(
                "Duplicate trade detected for "
                f"{trade_entry.date.isoformat()} {trade_entry.instrument} {trade_entry.direction} "
                f"{trade_entry.entry_time.isoformat()}."
            )
        if existing_page and duplicate_mode == "skip":
            sync_summary = self.sync_downstream_targets(
                trade_entry,
                existing_page,
                trade_journal_data_source_id=resolved_data_source_id,
            )
            logger.warning(
                "Skipping duplicate trade journal entry for %s because a matching page already exists: %s",
                trade_entry.trade_name,
                existing_page.get("url", existing_page.get("id")),
            )
            response = {
                "action": "skipped",
                "duplicate": True,
                "id": existing_page.get("id"),
                "url": existing_page.get("url"),
            }
            if sync_summary:
                response["sync"] = sync_summary
            return response

        screenshot_upload_id, screenshot_name, attachment_preview = self.prepare_screenshot_upload(
            screenshot_path=trade_entry.screenshot_path,
            screenshot_url=trade_entry.screenshot_url,
            dry_run=dry_run,
        )

        properties = build_notion_page_properties(
            trade_entry,
            screenshot_upload_id=screenshot_upload_id,
            screenshot_name=screenshot_name,
        )

        action = "updated" if existing_page else "created"
        request_body: dict[str, Any] = {"action": action, "properties": properties}
        if existing_page:
            request_body["page_id"] = existing_page["id"]
            request_body["page_url"] = existing_page.get("url")
        else:
            request_body["parent"] = {"type": "data_source_id", "data_source_id": resolved_data_source_id}
        if dry_run:
            if attachment_preview:
                request_body["attachment_preview"] = attachment_preview
                request_body["attachment_note"] = (
                    "Dry-run mode does not upload files. The Screenshot property will be populated after a live run."
                )
            return request_body

        if existing_page:
            response = self.client.update_page(existing_page["id"], properties)
            logger.info("Updated trade journal entry: %s", response.get("url", response.get("id")))
        else:
            response = self.client.create_page(resolved_data_source_id, properties)
            logger.info("Created trade journal entry: %s", response.get("url", response.get("id")))

        enriched_response = dict(response)
        enriched_response["action"] = action
        if existing_page:
            enriched_response["duplicate"] = True
        sync_summary = self.sync_downstream_targets(
            trade_entry,
            response,
            trade_journal_data_source_id=resolved_data_source_id,
        )
        if sync_summary:
            enriched_response["sync"] = sync_summary
        return enriched_response
