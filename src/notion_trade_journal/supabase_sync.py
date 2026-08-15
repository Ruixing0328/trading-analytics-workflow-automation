"""Sync helpers for copying the Notion journal into Supabase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import Settings
from .schema import TRADE_JOURNAL_PROPERTIES
from .service import TradeJournalService
from .supabase_client import SupabaseClient


def extract_plain_text(items: list[dict[str, Any]]) -> str | None:
    """Collapse a Notion rich text array into plain text."""

    parts: list[str] = []
    for item in items:
        plain_text = item.get("plain_text")
        if plain_text:
            parts.append(plain_text)
            continue
        text = item.get("text", {})
        content = text.get("content")
        if content:
            parts.append(content)
    combined = "".join(parts).strip()
    return combined or None


def deserialize_notion_property(property_value: dict[str, Any], notion_type: str) -> Any:
    """Convert a Notion page property into a flat Python value."""

    if notion_type == "title":
        return extract_plain_text(property_value.get("title", []))
    if notion_type == "rich_text":
        return extract_plain_text(property_value.get("rich_text", []))
    if notion_type == "date":
        date_value = property_value.get("date")
        return date_value.get("start") if date_value else None
    if notion_type == "select":
        select_value = property_value.get("select")
        return select_value.get("name") if select_value else None
    if notion_type == "number":
        return property_value.get("number")
    if notion_type == "checkbox":
        return property_value.get("checkbox")
    if notion_type == "files":
        return property_value.get("files", [])
    return None


def first_file_payload(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Flatten the first Screenshot file object into stable sync fields."""

    if not files:
        return {}

    file_object = files[0]
    file_type = file_object.get("type")
    nested = file_object.get(file_type or "", {})
    return {
        "screenshot_name": file_object.get("name"),
        "screenshot_url": nested.get("url"),
        "screenshot_source": file_type,
        "screenshot_expiry_time": nested.get("expiry_time"),
    }


def normalize_supabase_record(record: dict[str, Any]) -> dict[str, Any]:
    """Coerce fields into the stable shapes expected by the analytics table."""

    hold_minutes = record.get("hold_minutes")
    if isinstance(hold_minutes, float):
        # Keep duration math aligned with the rest of the project, which floors
        # partial-minute spans when deriving hold time from entry/exit timestamps.
        record["hold_minutes"] = int(hold_minutes)
    return record


def notion_page_to_supabase_record(page: dict[str, Any]) -> dict[str, Any]:
    """Convert a Notion page response into a Supabase row."""

    properties = page.get("properties", {})
    record: dict[str, Any] = {
        "notion_page_id": page.get("id"),
        "notion_page_url": page.get("url"),
        "notion_created_time": page.get("created_time"),
        "notion_last_edited_time": page.get("last_edited_time"),
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "raw_notion_page": page,
    }

    for definition in TRADE_JOURNAL_PROPERTIES:
        property_value = properties.get(definition.notion_name)
        if property_value is None:
            continue
        value = deserialize_notion_property(property_value, definition.notion_type)
        if definition.payload_key == "date":
            record["trade_date"] = value
            continue
        if definition.payload_key == "screenshot":
            record.update(first_file_payload(value))
            continue
        record[definition.payload_key] = value

    if record.get("trade_date") is None and record.get("entry_time"):
        record["trade_date"] = str(record["entry_time"])[:10]

    return normalize_supabase_record(record)


class SupabaseSyncService:
    """Copy the Trade Journal from Notion into Supabase for analytics."""

    def __init__(
        self,
        settings: Settings,
        *,
        supabase_client: SupabaseClient | None = None,
    ) -> None:
        self.settings = settings
        self.trade_service = TradeJournalService(settings)
        self.supabase_client = supabase_client or SupabaseClient.from_settings(settings)

    def sync_trades(
        self,
        *,
        data_source_id: str | None = None,
        validate_schema: bool = True,
        page_size: int = 100,
        batch_size: int = 200,
    ) -> dict[str, Any]:
        """Read every trade from Notion and upsert it into Supabase."""

        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")

        resolved_data_source_id = self.trade_service.resolve_data_source_id(data_source_id)
        if validate_schema:
            self.trade_service.validate_data_source_schema(resolved_data_source_id)

        pages = self.trade_service.client.iterate_data_source_pages(
            resolved_data_source_id,
            page_size=page_size,
        )

        batches = 0
        rows_upserted = 0
        batch: list[dict[str, Any]] = []

        for page in pages:
            batch.append(notion_page_to_supabase_record(page))
            if len(batch) < batch_size:
                continue
            rows_upserted += self.supabase_client.upsert_trades(batch)
            batches += 1
            batch = []

        if batch:
            rows_upserted += self.supabase_client.upsert_trades(batch)
            batches += 1

        return {
            "data_source_id": resolved_data_source_id,
            "pages_read": len(pages),
            "rows_upserted": rows_upserted,
            "batches": batches,
            "table": self.supabase_client.trades_table,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
