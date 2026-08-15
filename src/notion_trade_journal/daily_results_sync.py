"""Helpers for maintaining the Notion Daily Results database from trade pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


def _plain_text(items: list[dict[str, Any]]) -> str | None:
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


def _date_start(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    date_value = value.get("date")
    if not date_value:
        return None
    start = date_value.get("start")
    return str(start) if start else None


def _number_value(value: dict[str, Any] | None) -> float | None:
    if not value:
        return None
    number = value.get("number")
    return None if number is None else float(number)


def _select_value(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    select = value.get("select")
    if not select:
        return None
    name = select.get("name")
    return str(name) if name else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return datetime.fromisoformat(text)


@dataclass(frozen=True)
class DailyTradeSummaryRow:
    page_id: str | None
    page_url: str | None
    trade_name: str
    trade_date: str
    instrument: str | None
    direction: str | None
    result: str | None
    pnl: float | None
    entry_time: str | None


@dataclass(frozen=True)
class DailyResultsSummary:
    trade_date: str
    daily_result: str
    trade_count: int
    wins: int
    losses: int
    missing_pnl_trades: int
    net_pnl: float | None
    trades: tuple[DailyTradeSummaryRow, ...]


def trade_summary_row_from_page(page: dict[str, Any]) -> DailyTradeSummaryRow:
    """Extract the fields needed to build one Daily Results page."""

    properties = page.get("properties", {})
    trade_name = _plain_text(properties.get("Trade Name", {}).get("title", []))
    trade_date = _date_start(properties.get("Date")) or ""
    return DailyTradeSummaryRow(
        page_id=page.get("id"),
        page_url=page.get("url"),
        trade_name=trade_name or page.get("id") or "Untitled Trade",
        trade_date=trade_date[:10],
        instrument=_select_value(properties.get("Instrument")),
        direction=_select_value(properties.get("Direction")),
        result=_select_value(properties.get("Result")),
        pnl=_number_value(properties.get("P&L $")),
        entry_time=_date_start(properties.get("Entry Time")),
    )


def _daily_result_name(*, net_pnl: float | None, missing_pnl_trades: int, wins: int, losses: int) -> str:
    if missing_pnl_trades > 0:
        return "Incomplete"
    if wins == 0 and losses == 0:
        return "BE"
    if wins > 0 and losses == 0:
        return "Win"
    if losses > 0 and wins == 0:
        return "Loss"
    if (net_pnl or 0.0) > 0:
        return "Win"
    if (net_pnl or 0.0) < 0:
        return "Loss"
    return "BE"


def build_daily_results_summary(trade_date: date, trades: list[DailyTradeSummaryRow]) -> DailyResultsSummary:
    """Aggregate one day's trade rows into the Daily Results schema."""

    ordered = sorted(
        trades,
        key=lambda trade: (_parse_datetime(trade.entry_time) or datetime.min, trade.trade_name),
        reverse=True,
    )
    wins = sum(1 for trade in ordered if trade.result == "Win")
    losses = sum(1 for trade in ordered if trade.result == "Loss")
    missing_pnl_trades = sum(1 for trade in ordered if trade.pnl is None)
    net_pnl = None if missing_pnl_trades > 0 else sum((trade.pnl or 0.0) for trade in ordered)
    return DailyResultsSummary(
        trade_date=trade_date.isoformat(),
        daily_result=_daily_result_name(
            net_pnl=net_pnl,
            missing_pnl_trades=missing_pnl_trades,
            wins=wins,
            losses=losses,
        ),
        trade_count=len(ordered),
        wins=wins,
        losses=losses,
        missing_pnl_trades=missing_pnl_trades,
        net_pnl=net_pnl,
        trades=tuple(ordered),
    )


def _rich_text(content: str, *, link_url: str | None = None) -> dict[str, Any]:
    text: dict[str, Any] = {"content": content}
    if link_url:
        text["link"] = {"url": link_url}
    return {"type": "text", "text": text}


def _paragraph(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_rich_text(text)]},
    }


def _heading_2(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [_rich_text(text)]},
    }


def _format_pnl(value: float) -> str:
    if value > 0:
        return f"+${value:,.2f}"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return "$0.00"


def _trade_bullet(trade: DailyTradeSummaryRow) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [_rich_text(trade.trade_name, link_url=trade.page_url)]
    label_bits = [bit for bit in (trade.instrument, trade.direction) if bit]
    if label_bits:
        parts.append(_rich_text(" | "))
        parts.append(_rich_text(" ".join(label_bits)))
    if trade.result and trade.result not in {"Win", "Loss"} and trade.pnl is not None:
        parts.append(_rich_text(f" | {trade.result}"))
    if trade.pnl is None:
        parts.append(_rich_text(" | P&L missing"))
    else:
        parts.append(_rich_text(f" | {_format_pnl(trade.pnl)}"))
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": parts},
    }


def build_daily_results_page_children(summary: DailyResultsSummary) -> list[dict[str, Any]]:
    """Render the generated Daily Results page body."""

    children: list[dict[str, Any]] = []
    if summary.net_pnl is None:
        children.append(_paragraph("Net P&L: incomplete from source data"))
        children.append(_paragraph(f"Missing P&L Trades: {summary.missing_pnl_trades}"))
    else:
        children.append(_paragraph(f"Net P&L: {_format_pnl(summary.net_pnl)}"))
    children.append(_paragraph(f"Trade Count: {summary.trade_count}"))
    children.append(_paragraph(f"Wins: {summary.wins}"))
    children.append(_paragraph(f"Losses: {summary.losses}"))
    children.append(_heading_2("Trades"))
    children.extend(_trade_bullet(trade) for trade in summary.trades)
    return children


def build_daily_results_page_properties(summary: DailyResultsSummary) -> dict[str, dict[str, Any]]:
    """Build the Notion page properties for one Daily Results row."""

    return {
        "Day": {"title": [_rich_text(summary.trade_date)]},
        "Date": {"date": {"start": summary.trade_date}},
        "Daily Result": {"select": {"name": summary.daily_result}},
        "Trade Count": {"number": float(summary.trade_count)},
        "Wins": {"number": float(summary.wins)},
        "Losses": {"number": float(summary.losses)},
        "Missing P&L Trades": {
            "number": float(summary.missing_pnl_trades) if summary.missing_pnl_trades > 0 else None
        },
        "Net P&L": {"number": summary.net_pnl},
    }
