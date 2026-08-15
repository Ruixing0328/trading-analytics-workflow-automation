"""Mapping between validated trade entries and Notion page payloads."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from .constants import MAX_RICH_TEXT_CHUNK_LENGTH, SCREENSHOT_PROPERTY_NAME
from .models import TradeEntry
from .schema import PropertyDefinition, TRADE_JOURNAL_PROPERTIES


def build_notion_page_properties(
    trade_entry: TradeEntry,
    screenshot_upload_id: str | None = None,
    screenshot_name: str | None = None,
) -> dict[str, dict]:
    """Convert a validated trade entry into Notion page property values."""

    payload = trade_entry.model_dump(mode="python", exclude_none=True)
    properties: dict[str, dict] = {}

    for definition in TRADE_JOURNAL_PROPERTIES:
        if definition.notion_type == "files":
            continue
        if definition.payload_key not in payload:
            continue
        value = payload[definition.payload_key]
        if isinstance(value, str) and not value.strip():
            continue
        properties[definition.notion_name] = serialize_property_value(definition, value)

    if screenshot_upload_id:
        properties.update(build_screenshot_property(screenshot_upload_id, screenshot_name=screenshot_name))

    return properties


def build_screenshot_property(
    screenshot_upload_id: str,
    *,
    screenshot_name: str | None = None,
) -> dict[str, dict]:
    """Build the Notion Files & media property payload for one uploaded screenshot."""

    file_payload: dict[str, Any] = {
        "type": "file_upload",
        "file_upload": {"id": screenshot_upload_id},
    }
    if screenshot_name:
        file_payload["name"] = screenshot_name
    return {SCREENSHOT_PROPERTY_NAME: {"files": [file_payload]}}


def serialize_property_value(definition: PropertyDefinition, value: Any) -> dict:
    """Serialize one payload field into the Notion page property value format."""

    if definition.notion_type == "title":
        return {"title": rich_text_array(str(value))}
    if definition.notion_type == "rich_text":
        return {"rich_text": rich_text_array(str(value))}
    if definition.notion_type == "date":
        return {"date": {"start": serialize_date_value(value)}}
    if definition.notion_type == "select":
        select_name = value.value if isinstance(value, Enum) else str(value)
        return {"select": {"name": select_name}}
    if definition.notion_type == "number":
        return {"number": float(value)}
    if definition.notion_type == "checkbox":
        return {"checkbox": bool(value)}
    raise ValueError(f"Unsupported property type for mapping: {definition.notion_type}")


def serialize_date_value(value: date | datetime) -> str:
    """Serialize a date or datetime value into the Notion API date format."""

    if isinstance(value, datetime):
        return value.isoformat()
    return value.isoformat()


def rich_text_array(text: str) -> list[dict]:
    """Break long text into Notion-compatible rich text chunks."""

    cleaned = text.strip()
    if not cleaned:
        return []

    return [
        {"type": "text", "text": {"content": cleaned[index : index + MAX_RICH_TEXT_CHUNK_LENGTH]}}
        for index in range(0, len(cleaned), MAX_RICH_TEXT_CHUNK_LENGTH)
    ]
